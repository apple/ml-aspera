#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
"""Implements AnnotationManager and GenerationManager utilities classes which
are responsible for managing the writing and parsing the staging files and dataset
asset creation."""

import logging
import re
import shutil
from copy import deepcopy
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Literal, NamedTuple

from omegaconf import DictConfig
from rich.prompt import Prompt

from aspera.aliases import ProgramStr
from aspera.code_utils.utils import (
    get_imports,
    remove_import_statements,
    remove_module_comments,
)
from aspera.constants import (
    QUERY_FILE_EXTENSION,
    QUERY_ID_TO_SHARD_JSON,
    QUERY_TO_QUERY_ID_JSON,
    SHARD_SIZE,
    STAGING_EVAL_MODULE_BACKUP,
    STAGING_MODULE_BACKUP,
    STAGING_MODULE_NAME,
    STAGING_STATE_MODULE_BACKUP,
)
from aspera.dataset_schema import (
    AnnotatedDatapoints,
    DataPoint,
    DiscardedDataPoint,
    EditedDataPoint,
    EnvironmentState,
    cast_to_datapoint,
    get_eval_entry_point_code,
)
from aspera.interactive.console_messages import (
    CODE_CHECK,
    CODE_INSPECTION,
    CODE_PARSING_ERROR_FIX,
)
from aspera.interactive.display import _prompt_for_edit_error_correction
from aspera.parser import ProgramParserBasic, ProgramStringFinder, RemoveEntryPointCode
from aspera.readers import _get_last_shard, _get_shard_idx, load_json, load_nestedtext
from aspera.scenario import Scenario
from aspera.writers import save_json, save_nestedtext

logger = logging.getLogger(__name__)


class BackupFileIndex(NamedTuple):
    """Index the backup files."""

    query: int
    runtime_setup: int | None

    def index_file(self, fname: str) -> str:
        name, extension = fname.split(".")
        name = f"{name}_query_idx_{self.query}"
        if self.runtime_setup is not None:
            name = f"{name}_state_idx_{self.runtime_setup}"
        return f"{name}.{extension}"


def _dump_to_python_module(
    data: list[DataPoint],
    file: Path,
    scenario: Scenario,
    instructions: str | None = None,
    dump_runtime_setup_code: bool = False,
    dump_evaluation_code: bool = False,
    dump_entry_point_code: bool = True,
):
    """Create a python module containing the programs stored in `data`
    and dump it to `file`.

    Parameters
    ----------
    dump_runtime_setup_code
        If `True`, the query is automatically marked with the "OK" flag
        in the staging file and the programs setting up the state are
        dumped alongside the query execution program.
    dump_evaluation_code
        If `True`, the query execution, runtime state setup and evaluation
        code are dumped in a single file.
    dump_entry_point_code
        If True, code to run the evaluation is dumped in the annotation module.
    """
    content = get_imports(
        scenario,
        instructions,
        # import simulation tools if state generation code is inspected
        import_simulation_tools=dump_runtime_setup_code,
        import_testing_tools=dump_evaluation_code,
        # import the actual implementations rather than the docs
        executable=True,
    )
    for example in data:
        # the program has already been assessed for quality if we
        # are dumping the state generation code, so we mark it as OK
        # automatically
        if dump_runtime_setup_code:
            content.append("#OK:\n")
        content.append(f"# {example.query}\n")
        content.append(example.program)
        content.append("\n\n")
        if (
            dump_runtime_setup_code
            and (state_gen_programs := example.state_generation_programs) is not None
        ):
            for program in state_gen_programs:
                if dump_evaluation_code:
                    content.append("#OK:\n")
                content.append(program)
                content.append("\n\n")
        if (
            dump_evaluation_code
            and (eval_programs := example.evaluation_programs) is not None
        ):
            for program in eval_programs:
                content.append(program)
                content.append("\n\n")
    content.pop()

    with open(file, "w") as corrections_file:
        corrections_file.writelines(content)
        if dump_evaluation_code and dump_entry_point_code:
            assert len(data) == 1
            corrections_file.writelines(["\n\n", get_eval_entry_point_code(data[0])])


def _append_to_shard(
    data: (
        list[DataPoint]
        | list[EditedDataPoint]
        | list[DiscardedDataPoint]
        | list[EnvironmentState]
    ),
    dir_: Path,
    last_shard: Path = None,
    reader: Callable[[Path | str], list[dict[str, Any]]] = load_nestedtext,
    writer: Callable[[Any, Path], None] = save_nestedtext,
    extension: str = QUERY_FILE_EXTENSION,
):
    """Appends data to the last shard, creating a new shard if:

    - no shard exists
    - `data` contains more elements than can be added to the last shard given
        the `SHARD_SIZE` parameter
    """

    def _reindex_data(data: list[EditedDataPoint] | list[DataPoint], start: int):
        for i in range(len(data)):
            data[i]["query_id"] = str(start + i + 1)

    def _update_indices(data: list[dict[str, Any]], shard: Path):
        """Updates index files which allow us to track the queries across shards."""

        index_files = (
            shard.parent / QUERY_TO_QUERY_ID_JSON,
            shard.parent / QUERY_ID_TO_SHARD_JSON,
        )
        # create index files if they don't already exist
        for p in index_files:
            if not p.exists():
                save_json({}, p)
        updates = (
            {example["query"]: [example["query_id"]] for example in data},
            {example["query_id"]: [str(shard.name)] for example in data},
        )
        for index_file, update in zip(index_files, updates):
            current = load_json(index_file)
            try:
                assert all(k not in current for k in update), "Query already exists"
                current.update(update)
            except AssertionError:
                assert "corrections" in shard.parent.name
                for k in update:
                    if k in current:
                        current[k] += update[k]
                    else:
                        current[k] = [update[k]]
            save_json(current, index_file)

    def _timestamp(data: list[dict[str, Any]]):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for el in data:
            if "timestamp" not in el:
                el["timestamp"] = ts

    if not data:
        return
    if any(
        isinstance(
            el, (DataPoint, EditedDataPoint, DiscardedDataPoint, EnvironmentState)
        )
        for el in data
    ):
        data = [deepcopy(el.model_dump()) for el in data]
    else:
        data = [deepcopy(el) for el in data]
    _timestamp(data)
    last_shard = (
        _get_last_shard(dir_, extension=extension) if last_shard is None else last_shard
    )
    if last_shard is None:
        content = []
        logger.info(f"Creating shard queries_001.{extension} in {str(dir_)}")
        last_shard = dir_ / f"queries_001.{extension}"
        data = deepcopy(data)
        _reindex_data(data, 0)
    else:
        content = reader(last_shard)
        data = deepcopy(data)
        # ensure the query ids appended to the shard are always consecutive
        _reindex_data(data, int(content[-1]["query_id"]))

    capacity = SHARD_SIZE - len(content)
    if capacity:
        writer(content + data[:capacity], last_shard)
        _update_indices(data[:capacity], last_shard)
    if unsaved_data := data[capacity:]:
        shard_id = f"queries_{_get_shard_idx(last_shard) + 1:03}.{extension}"
        shard_pth = dir_ / shard_id
        logger.info(f"Creating shard {shard_id} in {str(dir_)}")
        writer(unsaved_data[:SHARD_SIZE], shard_pth)
        _update_indices(unsaved_data[:SHARD_SIZE], shard_pth)
        _append_to_shard(unsaved_data[SHARD_SIZE:], dir_, shard_pth)


class TypedComment(NamedTuple):

    content: str
    type: Literal["Feedback", "OK", "Quarantine"]


class QueryTypedComment(NamedTuple):
    query: str
    content: str
    type: Literal["Feedback", "OK", "Quarantine"]


def _parse_annotation_comments(code: str) -> list[TypedComment]:
    """Parse special comments made by the annotators along with their types."""
    comment_pattern = r"^\s*#\s*(Feedback|Quarantine|OK): *(.*)$"
    comments = []
    matches = re.finditer(comment_pattern, code, flags=re.MULTILINE)
    for match in matches:
        comment_type = match.group(1)
        comment_text = match.group(2).strip("\n ")
        comments.append(TypedComment(type=comment_type, content=comment_text))
    return comments


def _filter_imports(programs: list[str]) -> list[str]:
    """The LLM is instructed to import modules it uses during
    setup locally - this does not always happen, so we manually
    correct and filter the raw programs."""
    return [
        p for p in programs if not (p.startswith("import ") or p.startswith("from"))
    ]


def _parse_staging_file_to_comments_and_programs(
    stage_file: Path,
    comments_parser: Callable[
        [str], list[TypedComment] | list[QueryTypedComment]
    ] = _parse_annotation_comments,
) -> [list[TypedComment] | list[QueryTypedComment], list[ProgramStr]]:
    """Parse the programs and annotator comments from the staging file."""
    parser = ProgramParserBasic(
        preprocessor=ProgramStringFinder(start_seq=tuple(), end_seq=tuple())
    )
    while True:
        with open(stage_file, "r") as annotation_file:
            annotated_code = annotation_file.read()
        code = remove_import_statements(annotated_code, package_name=None).strip("\n")
        comments = comments_parser(code)
        code = remove_module_comments(code).strip("\n")
        programs = parser.parse(code)
        try:
            assert len(comments) == len(programs)
            break
        except AssertionError:
            print("comments", *comments, sep="\n")
            print("programs", *programs, sep="\n")
            _ = Prompt.ask(CODE_PARSING_ERROR_FIX)

    return comments, programs


def _parse_as_annotated_queries(
    data: list[DataPoint], comments: list[TypedComment], programs: list[ProgramStr]
) -> AnnotatedDatapoints:
    """Parse the corrected programs and annotator comments in structured format."""
    all_, discarded, edited, correct = [], [], [], []
    for i, (labeled_comment, program) in enumerate(zip(comments, programs)):
        match labeled_comment:
            case (comment, "Feedback"):
                updates = {"edited_program": program, "feedback": comment.strip("\n ")}
                new_datapoint: EditedDataPoint = EditedDataPoint(
                    **{**updates, **data[i].model_dump()}
                )
                edited.append(new_datapoint)
            case (comment, "Quarantine"):
                updates = {"comment": comment.strip("\n ")}
                new_datapoint: DiscardedDataPoint = DiscardedDataPoint(
                    **{**updates, **data[i].model_dump()}
                )
                discarded.append(new_datapoint)
            case (_, "OK"):
                new_datapoint: DataPoint = DataPoint(**data[i].model_dump())
                correct.append(new_datapoint)
            case _:
                raise ValueError("Could not match labelled comment")
        all_.append(new_datapoint)
    return AnnotatedDatapoints(
        **{"edited": edited, "discarded": discarded, "correct": correct, "all": all_}
    )


def _parse_query_execution_programs(
    stage_file: Path, data: list[DataPoint]
) -> AnnotatedDatapoints:
    """Parse query execution programs validated by the annotators."""
    comments, programs = _parse_staging_file_to_comments_and_programs(stage_file)
    return _parse_as_annotated_queries(data, comments, programs)


def _maybe_loop_until_edits_made(
    edited_programs: AnnotatedDatapoints, parsing_fcn: Callable, max_retries: int = 3
) -> AnnotatedDatapoints:
    i = 0
    while i < max_retries:
        edit_errors = [e for e in edited_programs.edited if e.misedited]
        if not edit_errors:
            return edited_programs
        _prompt_for_edit_error_correction(edit_errors)
        edited_programs = parsing_fcn()
        i += 1
    raise SyntaxError("Editing failed, possibly due to syntax errors")


def _annotate_query_execution(
    data: list[DataPoint],
    stage_file: Path,
    scenario: Scenario,
    instructions: str | None = None,
    max_retries: int = 3,
    *,
    parsing_fcn: Callable = None,
) -> AnnotatedDatapoints:
    """Dumps the data points into a staging directory,
    where they can be inspected by the data curator,
    discarded, annotated with edits and feedback or marked
    as correct."""
    annotation_module = stage_file.parent / STAGING_MODULE_NAME
    _dump_to_python_module(data, annotation_module, scenario, instructions=instructions)
    stage_dir = relative_to_root(annotation_module)
    logger.info(f"Data ready for inspection at {stage_dir}")
    _ = Prompt.ask(CODE_INSPECTION)
    annotated_queries: AnnotatedDatapoints = parsing_fcn(annotation_module, data)
    while True:
        try:
            assert len(annotated_queries.all) == len(data)
            break
        except AssertionError:
            _ = Prompt.ask(CODE_PARSING_ERROR_FIX)
            annotated_queries = parsing_fcn(annotation_module, data)
    annotated_queries = _maybe_loop_until_edits_made(
        annotated_queries,
        partial(parsing_fcn, annotation_module=annotation_module, data=data),
        max_retries=max_retries,
    )
    annotation_module_backup = stage_file.parent / STAGING_MODULE_BACKUP
    logger.info(f"Backed up query file to {annotation_module_backup}")
    shutil.copyfile(annotation_module, annotation_module_backup)
    return annotated_queries


def _parse_state_generation_programs(
    stage_file: Path, data: list[DataPoint]
) -> AnnotatedDatapoints:
    """Parse the state generation programs from the staging file.

    Returns
    -------
    AnnotatedDatapoints, where each datapoint represents a state generation program.
    These should be merged with the input data by the caller.
    """

    assert len(data) == 1, "Expected exactly one data point."
    comments, programs = _parse_staging_file_to_comments_and_programs(stage_file)
    query_comment, *comments = comments
    query_program, *programs = programs
    # programs generated by LLM, unedited
    raw_programs = _filter_imports(data[0].state_generation_programs)
    all_, discarded, edited, correct = [], [], [], []
    try:
        assert len(programs) == len(raw_programs)
    except AssertionError:
        logger.warning(
            f"Expected {len(raw_programs)} programs, got {len(programs)}. "
            "Ignore this warning if you added an additional state setup program."
        )
        # we can add additional state setup programs
        assert len(raw_programs) < len(programs)
        raw_programs = raw_programs + [None] * (len(programs) - len(raw_programs))
    for i, (input_program, maybe_edited_program, labelled_comment) in enumerate(
        zip(raw_programs, programs, comments)
    ):
        this_datapoint = {
            "query_id": data[0].query_id,
            "program": input_program,
            "scenario": data[0].scenario,
            "state_generation_programs": None,
            "query": data[0].query,
        }
        match labelled_comment:
            case (_, "OK"):
                # this occurs if the data curator adds another state generation
                # program to the file to simulate a different environment state
                if this_datapoint["program"] is None:
                    this_datapoint["program"] = maybe_edited_program
                datapoint = DataPoint(**this_datapoint)
                all_.append(datapoint)
                correct.append(datapoint)
            case (comment, "Feedback"):
                this_datapoint["edited_program"] = maybe_edited_program
                this_datapoint["feedback"] = comment
                datapoint = EditedDataPoint(**this_datapoint)
                all_.append(datapoint)
                edited.append(datapoint)
            case _:
                raise ValueError("Could not match labelled comment")
    return AnnotatedDatapoints(
        **{"edited": edited, "discarded": discarded, "correct": correct, "all": all_}
    )


def validate_input(
    data: list[EditedDataPoint] | list[DiscardedDataPoint] | list[DataPoint],
):
    match [e.contains_edits for e in data]:
        case [False]:
            pass
        case _:
            raise ValueError(
                "Expected a single DataPoint for state generation code validation"
            )


def _annotate_environment_state(
    data: list[DataPoint],
    stage_file: Path,
    scenario: Scenario,
    instructions: str | None = None,
    max_retries: int = 3,
    backup_file_index: BackupFileIndex | None = None,
) -> AnnotatedDatapoints:
    """Stage the query execution program along with LLM-generated code
    for generating the environment state for data curator inspection."""

    validate_input(data)
    annotation_module = stage_file.parent / STAGING_MODULE_NAME
    _dump_to_python_module(
        data,
        annotation_module,
        scenario,
        instructions=instructions,
        dump_runtime_setup_code=True,
    )
    stage_pth = relative_to_root(annotation_module)
    logger.info(f"Annotated state generation code ready for inspection at {stage_pth}")
    _ = Prompt.ask(CODE_CHECK)
    state_generation_programs = _parse_state_generation_programs(
        annotation_module, data
    )
    # handle cases where the user forgets to actually edit the program (happens more
    #  often than you think )
    state_generation_programs = _maybe_loop_until_edits_made(
        state_generation_programs,
        partial(
            _parse_state_generation_programs, stage_file=annotation_module, data=data
        ),
        max_retries=max_retries,
    )
    backup_staging_file(
        annotation_module, stage_file, backup_file_index, STAGING_STATE_MODULE_BACKUP
    )
    return state_generation_programs


def backup_staging_file(
    annotation_module: Path,
    stage_file: Path,
    backup_file_index: BackupFileIndex,
    backup_file_name: str,
):
    """Backup the staging file so that curated programs are saved in case the
    program crashes (eg due to hanging OpenAI requests)."""
    if backup_file_index is not None:
        backup_file_name = backup_file_index.index_file(backup_file_name)
    annotation_module_backup = relative_to_root(stage_file.parent / backup_file_name)
    logger.info(f"Backing up staging file to {annotation_module_backup}")
    shutil.copyfile(annotation_module, stage_file.parent / backup_file_name)


def _parse_evaluation_programs(
    stage_file: Path, data: list[DataPoint]
) -> AnnotatedDatapoints:
    """Parse the evaluation code from the staging file."""

    assert len(data) == 1, "Expected exactly one data point."
    comments, programs = _parse_staging_file_to_comments_and_programs(stage_file)
    processor = RemoveEntryPointCode()
    # first two programs are the execution & runtime setup
    comments = comments[2:]
    programs = programs[2:]

    raw_programs = data[0].evaluation_programs
    all_, discarded, edited, correct = [], [], [], []
    # try:
    assert len(raw_programs) == len(
        programs
    ), "The number of evaluation programs staged does not match the number parsed"
    for i, (input_program, maybe_edited_program, labelled_comment) in enumerate(
        zip(raw_programs, programs, comments)
    ):
        this_datapoint = {
            "query_id": data[0].query_id,
            "program": input_program,
            "scenario": data[0].scenario,
            "state_generation_programs": None,
            "query": data[0].query,
        }
        match labelled_comment:
            case (_, "OK"):
                # add runner template to the program
                datapoint = DataPoint(**this_datapoint)
                all_.append(datapoint)
                correct.append(datapoint)
            case (comment, "Feedback"):
                # the edited program is parsed from a file where we dump
                # entry point code which we don't need
                this_datapoint["edited_program"] = processor(maybe_edited_program)
                this_datapoint["feedback"] = comment
                datapoint = EditedDataPoint(**this_datapoint)
                all_.append(datapoint)
                edited.append(datapoint)
            case _:
                raise ValueError("Could not match labelled comment")
    return AnnotatedDatapoints(
        **{"edited": edited, "discarded": discarded, "correct": correct, "all": all_}
    )


def _annotate_evaluation(
    data: list[DataPoint],
    stage_file: Path,
    scenario: Scenario,
    instructions: str | None = None,
    max_retries: int = 3,
    backup_file_index: BackupFileIndex | None = None,
) -> AnnotatedDatapoints:
    """Stage the query execution program along with LLM-generated code
    for generating the runtime state and the evaluation function
    for data curator inspection."""
    validate_input(data)
    annotation_module = stage_file.parent / STAGING_MODULE_NAME
    _dump_to_python_module(
        data,
        annotation_module,
        scenario,
        instructions=instructions,
        dump_runtime_setup_code=True,
        dump_evaluation_code=True,
    )
    stage_pth = relative_to_root(annotation_module)
    logger.info(f"Evaluation code ready for inspection at {stage_pth}")
    _ = Prompt.ask(CODE_CHECK)
    eval_programs = _parse_evaluation_programs(annotation_module, data)
    eval_programs = _maybe_loop_until_edits_made(
        eval_programs,
        partial(_parse_evaluation_programs, stage_file=annotation_module, data=data),
        max_retries=max_retries,
    )
    backup_staging_file(
        annotation_module, stage_file, backup_file_index, STAGING_EVAL_MODULE_BACKUP
    )
    return eval_programs


def _quarantine(data: list[DiscardedDataPoint], quarantine_dir: Path):
    """Dumps the data points into a quarantine directory. These
    datapoints are marked as "quarantined" because they may describe
    low quality queries or queries that require more discussion
    prior to including in the dataset."""
    _append_to_shard(data, quarantine_dir)


def _stage_plan_corrections(
    data: list[EditedDataPoint],
    correction_dir: Path,
):
    """Append the edited programs to a separate corpus containing
    the generated programs and their edits."""
    _append_to_shard(data, correction_dir)


def _append_to_plans_corpus(data: list[DataPoint | EditedDataPoint], corpus_dir: Path):
    """Extend the main dataset which contains queries and plan annotations."""
    data = [cast_to_datapoint(datapoint) for datapoint in data]
    _append_to_shard(data, corpus_dir)


class AnnotationManager:

    def __init__(self, config: DictConfig):
        self._config = config
        self._state_generation_correction_dir = Path(
            config.state_generation_correction_dir
        )
        self._eval_correction_dir = Path(config.eval_correction_dir)
        self._corpus_dir = Path(config.corpus_dir)
        self._modules_dir = Path(config.modules_dir)
        self.annotate_query_execution = partial(
            _annotate_query_execution,
            stage_file=Path(config.stage_file),
            instructions=config.instructions,
            parsing_fcn=_parse_query_execution_programs,
        )
        self._annotate_state = partial(
            _annotate_environment_state,
            stage_file=Path(config.stage_file),
            instructions=config.state_generation_instructions,
        )
        self._quarantine = partial(
            _quarantine, quarantine_dir=Path(config.quarantine_dir)
        )
        self._annotate_evaluation = partial(
            _annotate_evaluation,
            stage_file=Path(config.stage_file),
            instructions=config.evaluation_instructions,
        )
        self.stage_plan_corrections = partial(
            _stage_plan_corrections,
            correction_dir=Path(config.corrections_dir),
        )
        self.stage_plans = partial(
            _append_to_plans_corpus, corpus_dir=Path(config.corpus_dir)
        )
        self.stage_databases = partial(
            _append_to_shard,
            dir_=Path(config.database_dir),
            writer=save_json,
            reader=load_json,
            extension="json",
        )
        self.stage_python_modules = partial(
            self._stage_python_modules,
            include_state_generation_code=config.generate_environment_state_setup_code,
            include_evaluation_code=config.generate_eval_code,
        )
        # create a recovery file where you can paste the relevant bits
        # from an unparseable completion if the parser fails
        Path(config.recovery_file).touch(exist_ok=True)

    def quarantine(self, datapoints: list[DiscardedDataPoint]):
        """The curator may identify data points which require further
        discussion prior to being included in the corpus. These are filtered
        from the `datapoints` and moved to quarantine shards, stored with
        each scenario outputs."""
        if not datapoints:
            return
        self._quarantine(datapoints)

    def annotate_environment_state(
        self,
        data: list[DataPoint],
        scenario: Scenario,
        backup_file_index: BackupFileIndex | None = None,
    ) -> AnnotatedDatapoints:
        """Dumps the query and the state generation code to the staging file and
        parses the state generation programs after inspection by the data curator.

        Returns
        -------
        AnnotatedDatapoints, where each datapoint contains the code for state
        generation and corrections to the raw data, if applicable.
        """
        state_generation_code: AnnotatedDatapoints = self._annotate_state(
            data=data, scenario=scenario, backup_file_index=backup_file_index
        )
        # capture edits to separate corpus
        edits = deepcopy(state_generation_code.edited)
        if edits:
            _stage_plan_corrections(edits, self._state_generation_correction_dir)
        return state_generation_code

    def annotate_evaluation(
        self,
        data: list[DataPoint],
        scenario: Scenario,
        backup_file_index: BackupFileIndex | None = None,
    ) -> AnnotatedDatapoints:
        eval_code: AnnotatedDatapoints = self._annotate_evaluation(
            data=data,
            scenario=scenario,
            backup_file_index=backup_file_index,
        )
        edits: list[EditedDataPoint] = deepcopy(eval_code.edited)
        if edits:
            _stage_plan_corrections(edits, self._eval_correction_dir)
        return eval_code

    def get_query_id(self, query: str) -> str | None:
        """Look-up the ID of a particular query in the corpus.

        Returns
        -------
        A str representing the ID of the query or None if the query wasn't found.
        """
        query_to_query_id = load_json(self._corpus_dir / QUERY_TO_QUERY_ID_JSON)
        if query in query_to_query_id:
            assert len(query_to_query_id[query]) == 1
            return query_to_query_id[query][0]
        return

    def _stage_python_modules(
        self,
        data: AnnotatedDatapoints,
        scenario: Scenario,
        include_state_generation_code: bool = False,
        include_evaluation_code: bool = False,
    ):
        for data_point in data.all:
            query_id = self.get_query_id(data_point.query)
            _dump_to_python_module(
                [cast_to_datapoint(data_point)],
                self._modules_dir / f"query_{query_id}.py",
                scenario,
                dump_runtime_setup_code=include_state_generation_code,
                dump_evaluation_code=include_evaluation_code,
                dump_entry_point_code=False,
            )

    def save_assets(
        self,
        data: AnnotatedDatapoints,
        scenario: Scenario,
        runtime_simulation_tools: list[str] | None = None,
        execution_evaluation_tools: list[str] | None = None,
    ):
        """Update the corpus assets with the new data.

        Parameters
        ----------
        runtime_simulation_tools
            The additional tools the data curator prompted the LLM to generate the
            environment state.
        execution_evaluation_tools
            The additional tools the data curator prompted the LLM with to
            verify the execution correctness
        """

        scenario = deepcopy(scenario)
        scenario.simulation_tools = runtime_simulation_tools
        scenario.evaluation_tools = execution_evaluation_tools
        # save the entire scenario to the corpus
        for data_point in data.correct + data.edited:
            data_point.scenario = scenario
        # discard any queries that need discussion, were poor quality
        # or are not supported by the codebase
        self._quarantine(data.discarded)
        # merge the annotated data into the corpus
        self.stage_plans(data.correct + data.edited)
        # create a separate corpus with paired generated and edited programs
        self.stage_plan_corrections(data.edited)
        self.stage_python_modules(
            data,
            scenario=scenario,
        )


def _parse_annotation_comments_and_queries(code: str) -> list[QueryTypedComment]:
    # Regular expression to match the comments
    pattern = re.compile(r"#\s*(OK|Feedback|Quarantine): *(.*)\n#\s*Query:\s*(.*)")

    matches = pattern.findall(code)
    results = [
        QueryTypedComment(query=query.strip(), content=content.strip(), type=type_)
        for type_, content, query in matches
    ]
    return results


def _parse_generated_queries(
    stage_file: Path, data: list[DataPoint]
) -> AnnotatedDatapoints:
    """Parse the queries and the execution plans validated by
    the annotators."""
    comments, programs = _parse_staging_file_to_comments_and_programs(
        Path(stage_file), comments_parser=_parse_annotation_comments_and_queries
    )
    assert (
        len(comments) == len(programs) == len(data)
    ), "Mismatch between number of data points and number of comments"

    all_, discarded, edited, correct = [], [], [], []
    for i, (example, comment, program) in enumerate(zip(data, comments, programs)):
        example.query = comment.query
        match comment:
            case (_, content, "Feedback"):
                updates = {"edited_program": program, "feedback": content.strip("\n ")}
                new_datapoint: EditedDataPoint = EditedDataPoint(
                    **{**updates, **data[i].model_dump()}
                )
                edited.append(new_datapoint)
            case (_, content, "Quarantine"):
                updates = {"comment": content.strip("\n ")}
                new_datapoint: DiscardedDataPoint = DiscardedDataPoint(
                    **{**updates, **data[i].model_dump()}
                )
                discarded.append(new_datapoint)
            case (_, _, "OK"):
                new_datapoint: DataPoint = DataPoint(**data[i].model_dump())
                correct.append(new_datapoint)
            case _:
                raise ValueError("Could not match labelled comment")
        all_.append(new_datapoint)

    return AnnotatedDatapoints(
        **{"edited": edited, "discarded": discarded, "correct": correct, "all": all_}
    )


class GenerationManager(AnnotationManager):
    def __init__(self, config: DictConfig):
        super().__init__(config.annotation)
        self.inspect_queries_and_execution_plans = partial(
            _annotate_query_execution,
            stage_file=Path(config.annotation.stage_file),
            instructions=config.annotation.instructions,
            parsing_fcn=_parse_generated_queries,
        )


def relative_to_root(path: Path) -> Path:
    import aspera

    return path.relative_to(Path(aspera.__file__).parent.parent.parent)
