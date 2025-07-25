#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import importlib
import logging
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

from hydra.utils import instantiate
from omegaconf import DictConfig
from pydantic import BaseModel
from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme

from aspera.aliases import ProgramStr, SimulationModuleName, SimulationToolName
from aspera.apps_implementation.exceptions import assert_requires_input_error
from aspera.code_utils.utils import get_imports, is_import
from aspera.completer.completer import LLMPrompt
from aspera.completer.openai_completer import OpenAiChatCompleter
from aspera.completer.utils import MessageList, print_messages
from aspera.constants import (
    EVALUATION_TOOLS_IMPLEMENTATIONS_PATH,
    EVALUATION_TOOLS_PATH,
    RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX,
    SIMULATION_TOOLS_IMPLEMENTATIONS_PATH,
    SIMULATION_TOOLS_PATH,
)
from aspera.dataset_schema import (
    AnnotatedDatapoints,
    DataPoint,
    EditedDataPoint,
    EnvironmentState,
    SessionLog,
    function_name_parser,
)
from aspera.interactive.annotation_manager import AnnotationManager, BackupFileIndex
from aspera.interactive.console_messages import (
    EVAL_CODE_GENERATION_CONFIRMATION,
    EVALUATION_TOOLS_IMPLEMENTATION,
    EVALUATION_TOOLS_NOTIFICATION,
    PARSING_FAILED,
    RECOVERY_FILE_POPULATED_CONFIRMATION,
    SIMULATION_TOOLS_IMPLEMENTATION,
    SIMULATION_TOOLS_NOTIFICATION,
)
from aspera.interactive.display import (
    display_executable_and_runtime_setup_programs,
    display_simulation_tools,
)
from aspera.interactive.utils import save_progress
from aspera.parser import (
    ExtractFunctionName,
    ProgramParserBasic,
    ProgramParserWithImportHandling,
    ProgramStringFinder,
)
from aspera.prompting.prompt_utils import parse_tools
from aspera.prompting.system_turn_prompts import SystemTurnTemplate
from aspera.prompting.user_turn_prompts import (
    EvaluationCodeGenerationUserTurnTemplate,
    RuntimeEnvironmentSetupUserTurnTemplate,
)
from aspera.readers import count_shards, load_json
from aspera.scenario import Scenario
from aspera.simulation.execution_context import ExecutionContext, new_context
from aspera.simulation.execution_environment import ExecutionEnvironment

logger = logging.getLogger(__name__)


class LLMOutput(BaseModel):

    programs: list[str]
    completion: str


class InteractiveSession:
    def __init__(self, config: DictConfig):
        self.config = instantiate(config)
        self._session_id = count_shards(config.output_dir, extension="json")
        logger.info(f"Session ID: {self._session_id}")
        self._completer = OpenAiChatCompleter(**instantiate(config.completer_args))
        self._completer_timeout = config.completer_args.get("timeout", None)
        self._max_retries = config.completer_args.get("max_retries", 1)
        self._odir = Path(config.output_dir)
        self._scenario = Scenario.model_validate(
            {
                "apps": config.apps,
                "query_solution": config.examples.query_solution,
                "runtime_setup": config.examples.runtime_setup,
                "evaluation": config.examples.evaluation,
                "guidelines": config.guidelines,
                "simulation_tools": config.simulation_tools,
                "evaluation_tools": config.evaluation_tools,
            }
        )
        self._selected_simulation_tools: list[str] | None = None
        self._selected_evaluation_tools: list[str] | None = None
        self._simulate_env_state = (
            config.annotation.generate_environment_state_setup_code
        )
        self._generate_eval_code = config.annotation.generate_eval_code
        if self._generate_eval_code:
            assert (
                self._simulate_env_state
            ), "Runtime state must be generated before evaluation"
        self._show_simulation_tools = config.annotation.show_simulation_tools
        self._session_manager = AnnotationManager(config.annotation)
        self._parser: ProgramParserWithImportHandling = self.config.parser.parser
        # parser used to parse a data curator written recovery python module
        # in case a completion cannot be parsed with the above parser
        self._backup_parser = ProgramParserBasic(
            preprocessor=ProgramStringFinder(start_seq=tuple(), end_seq=tuple())
        )
        self._templates = self.config.turn_templates
        self._show_messages = config.annotation.show_prompt
        self.processed_queries: list[str] = []
        self._chat_history: MessageList = []
        self._session_log: SessionLog | None = None
        if (restore_path := config.annotation.restore_path) is not None:
            self._session_log = self.get_log(restore_path)
            self._completer.budget_info = self._session_log.budget
        self._initialise()
        self._save = partial(
            save_progress, session_id=self._session_id, odir=self._odir
        )
        custom_theme = Theme(
            {"info": "bold green", "warning": "magenta", "danger": "bold red"}
        )
        self._console = Console(theme=custom_theme)
        self._execution_environment = ExecutionEnvironment()
        self._function_name_parser = ExtractFunctionName()
        self._serialise_state = False

    @staticmethod
    def get_log(path: str) -> SessionLog:
        """Load the transcript (ie message sequence) of the
        last interaction with the agent."""
        return SessionLog.model_validate(load_json(path)[-1])

    def _initialise_chat_history(self):
        """Initialise the interactive session with the agent. If the
        session is restored, the messages are the chat history. Otherwise,
        the messages are initialised with the system turn."""
        # start a new session - initialise the system message from the template
        if self._session_log is None:
            templates = self.config.turn_templates
            messages = [
                SystemTurnTemplate(template_factory=templates.system).get_prompt(
                    self._scenario
                ),
            ]
            self._chat_history = messages
            logger.info("Initialising chat history...")
            return
        # restore the messages exchanged in the last interaction, up to
        # and excluding the last agent response
        logger.info("Restoring chat history from previous session...")
        saved_messages = self._session_log.chat_history
        self._chat_history = saved_messages

    def _initialise_queries(self):
        """Remember queries that have already been annotated or generated, t
        to support skipping them if annotation proceeds over multiple
        interactive sessions or generate diverse queries."""
        if self._session_log is None:
            self.processed_queries = []
            return
        logger.info("Loading previously generated queries")
        self.processed_queries = self._session_log.queries

    def _initialise(self):
        """Initialise the session messages and annotated/generated
        query history."""
        self._initialise_chat_history()
        self._initialise_queries()

    def _prompt_user_for_simulation_tool_selection(
        self, scenario: Scenario
    ) -> Scenario:
        """Prompts the data curator with a table showing tools available for simulating
        the runtime environment, reloading the relevant modules if the data curator implements
        a new simulation tool."""

        def validate_response(user_response: str):
            assert all("::" in s for s in user_response.split(","))

        if not self._show_simulation_tools or scenario.simulation_tools is None:
            return scenario
        self._console.print(
            SIMULATION_TOOLS_IMPLEMENTATION,
            style="info",
        )
        default_tools = parse_tools(scenario.simulation_tools)
        self._console.print(
            display_simulation_tools(default_tools, SIMULATION_TOOLS_PATH)
        )
        while True:
            # noqa
            user_response = Prompt.ask(
                SIMULATION_TOOLS_NOTIFICATION, default="no"
            ).strip()
            if user_response in {"no"}:
                self._selected_simulation_tools = scenario.simulation_tools
                return scenario
            try:
                validate_response(user_response)
            except AssertionError:
                self._console.print("Invalid input. Please try again.", style="danger")
                user_response = Prompt.ask(
                    SIMULATION_TOOLS_NOTIFICATION, default="no"
                ).strip()
            user_configured_tools = [t.strip() for t in user_response.split(",")]
            self._selected_simulation_tools = user_configured_tools
            self.reload_modules(
                user_configured_tools,
                docs_tool_path=SIMULATION_TOOLS_PATH,
                tool_impl_path=SIMULATION_TOOLS_IMPLEMENTATIONS_PATH,
            )
            scenario = deepcopy(scenario)
            scenario.simulation_tools = user_configured_tools
            return scenario

    @staticmethod
    def reload_modules(tools: list[str], docs_tool_path: str, tool_impl_path: str):
        """Reload the modules where tools are implemented.

        Parameters
        ----------
        tools
            A list of str, where each element is in the format module::tool
        docs_tool_path
            The path to the modules where `tools` are documented.
        tool_impl_path
            The path to the modules where `tools` are implemented.
        """
        parsed_tools: dict[SimulationModuleName, list[SimulationToolName]] = (
            parse_tools(tools)
        )
        for module_name in parsed_tools:
            module = importlib.import_module(f"{docs_tool_path}.{module_name}")
            impl_module = importlib.import_module(f"{tool_impl_path}.{module_name}")
            importlib.reload(module)
            importlib.reload(impl_module)

    def get_session_state(
        self, completion: str, messages: MessageList
    ) -> dict[str, Any]:
        session_state = {
            "chat_history": messages,
            "last_user_turn": messages[-1]["content"],
            "completion": completion,
            "queries": self.processed_queries,
            "budget": self._completer.budget_info,
        }
        return session_state

    def _parse_completion(self, completion: str) -> LLMOutput:
        """Parse the completion, involving the user if there
        are any faults that break the parser."""
        try:
            parsed_programs = self._parser.parse(completion)
            programs = []
            for program in parsed_programs:
                if is_import(program):
                    logger.info("Ignoring import statement")
                    print(program)
                else:
                    programs.append(program)
        except Exception:
            self._console.print(PARSING_FAILED)
            print(completion)
            _ = Prompt.ask(RECOVERY_FILE_POPULATED_CONFIRMATION)
            with open(self.config.annotation.recovery_file, "r") as f:
                code = f.read().strip("\n ")
            programs = self._backup_parser.parse(code)
        if len(programs) > 1:
            logger.warning(
                "Multiple programs found during generation. "
                "This is expected only if you are labelling or "
                "generating a batch of queries or you added an"
                "additional runtime initialisation program."
            )
        return LLMOutput(programs=programs, completion=completion)

    def _generate_programs(
        self,
        messages: MessageList,
        log_name: str,
        log_opts: dict[str, Any] | None = None,
    ) -> LLMOutput:
        """Call the LLM and return a list of generated programs

        Parameters
        ----------
        log_name
            The chat history is saved under this name.
        log_opts
            Optional arguments for the _save method.

        """
        if self._show_messages:
            print_messages(messages)
        llm_prompt = LLMPrompt(messages=messages)
        completion = self._completer.complete(
            llm_prompt,
            timeout=self._completer_timeout,
            max_retries=self._max_retries,
        )
        session_state = self.get_session_state(completion, messages)
        log_opts = log_opts or {}
        self._save(**session_state, log_name=log_name, **log_opts)
        return self._parse_completion(completion)

    def _maybe_generate_environment_setup_code(
        self,
        messages: MessageList,
        annotated_queries: AnnotatedDatapoints,
    ) -> AnnotatedDatapoints | None:
        """Follow-up call to the LLM to generate the state of the environment for each
        annotated query. After the program which sets the state is generated and possibly
        edited by the data curator, it is saved in the `state_generation_programs`
        field of the corresponding datapoint.
        """
        if not self._simulate_env_state:
            return
        messages = deepcopy(messages)
        for i, example in enumerate(
            annotated_queries.correct + annotated_queries.edited
        ):
            self._prepare_for_runtime_state_generation(example, messages)
            llm_output = self._generate_programs(
                messages, f"state_annotation_tmp_id_{example.query_id}"
            )
            messages.pop()
            messages.pop()
            self._annotate_runtime_state(
                example, llm_output, backup_file_index=BackupFileIndex(i, None)
            )

    def _prepare_for_runtime_state_generation(
        self, example: DataPoint | EditedDataPoint, messages: MessageList
    ):
        """Extend chat history with assistant and user turns relevant for runtime
        state generation."""
        messages.append({"role": "assistant", "content": example.curated_program})
        # create a new scenario containing possibly updated simulation
        # tools compared to the default
        scenario = self._prompt_user_for_simulation_tool_selection(
            scenario=self._scenario,
        )
        # follow-up user turn prompting the agent to generate state
        user_turn_template = RuntimeEnvironmentSetupUserTurnTemplate(
            template_factory=self._templates.user_environment_setup_request
        )
        state_function_def = user_turn_template.render_runtime_setup_program_templ(
            example
        )
        messages.append(
            user_turn_template.get_prompt(
                scenario,
                plan_name=example.plan_name,
                setup_function_name=example.setup_function_name,
                state_function_def=state_function_def,
            )
        )

    def _annotate_runtime_state(
        self,
        example: DataPoint | EditedDataPoint,
        llm_output: LLMOutput,
        backup_file_index: BackupFileIndex,
    ):
        """Invoke the annotation manager to trigger the user interaction for verifying the
        code that sets up the runtime state."""
        # pass a DataPoint to the annotation manager to annotate state generation code
        match example.contains_edits:
            case False:
                state_annotated_example = DataPoint(
                    **{
                        **example.model_dump(),
                        "state_generation_programs": llm_output.programs,
                    }
                )
            case True:
                data = {
                    "program": example.edited_program,
                    "state_generation_programs": llm_output.programs,
                }
                for field in DataPoint.model_fields:
                    if field not in data:
                        data[field] = getattr(example, field)
                state_annotated_example = DataPoint(**data)
            case _:
                raise TypeError(f"Unexpected example type: {type(example)}")
        # these datapoints contain the stage generation code (which is possibly edited) ...
        state_generation_code: AnnotatedDatapoints = (
            self._session_manager.annotate_environment_state(
                data=[state_annotated_example],
                scenario=self._scenario,
                backup_file_index=backup_file_index,
            )
        )
        example.update_with_runtime_state_generation_programs(state_generation_code)

    def _confirm_eval_code_generation(
        self, query: str, executable: ProgramStr, runtime_setup: ProgramStr
    ) -> bool:
        """Prompts the data curator to enquire if an evaluation function
        should be generated given the program and runtime setup program. Evaluation
        may be skipped, for example, if the simulation does not yet handle a particular
        runtime state (eg implemented search semantics is different to the runtime setup)
        but may be updated in the future.
        """

        self._console.print(
            display_executable_and_runtime_setup_programs(
                query,
                executable,
                runtime_setup,
            )
        )
        response = Prompt.ask(
            EVAL_CODE_GENERATION_CONFIRMATION, default="yes", choices=["yes", "no"]
        ).strip()
        return True if response == "yes" else False

    def _maybe_sanitise_execution_programs(self, programs: list[ProgramStr]):
        """The LLM might randomly drop the program for runtime state setup
        in the prompt, which would cause an assertion. We filter them out
        to prevent this error."""
        keep = []
        for p in programs:
            if self._function_name_parser(p).startswith(
                RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX
            ):
                logger.warning(
                    "A runtime setup program was detected while parsing evaluation code. Ignoring"
                )
                self._console.print(p)
                continue
            keep.append(p)
        return keep

    def _maybe_generate_execution_test_code(
        self,
        messages: MessageList,
        annotated_queries: AnnotatedDatapoints,
    ) -> AnnotatedDatapoints | None:
        """Follow-up call to the LLM to generate evaluation code for give the query
        and runtime states generated. After the test program is possibly edited by
        the data curator, it is saved in the `evaluation_code` variable.
        field of the corresponding datapoint.
        """
        if not self._generate_eval_code:
            return
        messages = deepcopy(messages)
        for i, example in enumerate(
            annotated_queries.correct + annotated_queries.edited
        ):
            evaluation_programs: list[str] = []
            for j, runtime_setup_program in enumerate(
                example.state_generation_programs
            ):
                should_generate = self._confirm_eval_code_generation(
                    example.query, example.curated_program, runtime_setup_program
                )
                template = EvaluationCodeGenerationUserTurnTemplate
                user_turn_template: EvaluationCodeGenerationUserTurnTemplate = template(
                    template_factory=self._templates.user_evaluation_code_generation
                )
                if not should_generate:
                    default_eval_function = (
                        user_turn_template.render_skip_eval_template(example)
                    )
                    evaluation_programs.append(default_eval_function)
                    continue
                self._prepare_for_eval_program_generation(
                    example, messages, runtime_setup_program
                )
                llm_output = self._generate_programs(
                    messages, log_name=f"eval_annotation_tmp_id_{example.query_id}"
                )
                messages.pop()
                messages.pop()
                backup_file_index = BackupFileIndex(i, j)
                evaluation_code = self._annotate_evaluation(
                    example, llm_output, backup_file_index, runtime_setup_program
                )
                assert (
                    len(evaluation_code.all) == 1
                ), "Expected only one evaluation function"
                match evaluation_code.all[0].contains_edits:
                    case True:
                        evaluation_programs.append(
                            evaluation_code.edited[0].edited_program
                        )
                    case False:
                        evaluation_programs.append(evaluation_code.correct[0].program)
            assert len(evaluation_programs) == len(
                example.state_generation_programs
            ), "Number of evaluation programs does not match the number of runtime setup programs"
            example.evaluation_programs = evaluation_programs

    def _annotate_evaluation(
        self,
        example: DataPoint | EditedDataPoint,
        llm_output: LLMOutput,
        backup_file_index: BackupFileIndex,
        runtime_setup_program: ProgramStr,
    ) -> AnnotatedDatapoints:
        """Invoke the annotation manager to trigger the user interaction for verifying
        the test code for query execution."""
        programs = llm_output.programs
        programs = self._maybe_sanitise_execution_programs(programs)
        try:
            assert programs
        except AssertionError:
            logger.error(
                "No execution evaluation code was generated. See completion below"
            )
            self._console.print(llm_output.completion)
        this_example_data = example.model_dump()
        this_example_data["state_generation_programs"] = [runtime_setup_program]
        this_example_data["evaluation_programs"] = programs
        this_example_data["program"] = example.curated_program
        eval_state_annotated_program = DataPoint(**this_example_data)
        evaluation_code: AnnotatedDatapoints = (
            self._session_manager.annotate_evaluation(
                data=[eval_state_annotated_program],
                scenario=self._scenario,
                backup_file_index=backup_file_index,
            )
        )
        return evaluation_code

    def _prepare_for_eval_program_generation(
        self,
        example: DataPoint | EditedDataPoint,
        messages: MessageList,
        runtime_setup_program: ProgramStr,
    ):
        """Extend chat history with assistant and user turns relevant for evaluation program
        generation."""
        template = EvaluationCodeGenerationUserTurnTemplate
        user_turn_template: EvaluationCodeGenerationUserTurnTemplate = template(
            template_factory=self._templates.user_evaluation_code_generation
        )
        messages.append({"role": "assistant", "content": example.curated_program})
        scenario = self._prompt_user_for_evaluation_tool_selection(
            scenario=self._scenario
        )
        setup_progr_name = function_name_parser(runtime_setup_program)
        messages.append(
            user_turn_template.get_prompt(
                scenario,
                plan_name=example.plan_name,
                setup_function_name=setup_progr_name,
                test_function_name=example.test_function_name,
                runtime_setup_program=runtime_setup_program,
                eval_function_def=user_turn_template.render_eval_program_templ(
                    example, runtime_setup_program
                ),
            )
        )

    def _save_environment_state(self, annotated_queries: AnnotatedDatapoints):
        """If the annotation session is configured to generate code that initialises
        the databases, this code executed to generate the environment initial state.
        Given this initial state, the query execution code is run to generate the final
        state. The states are saved together with the query."""
        if not self._simulate_env_state or not self._serialise_state:
            return
        # this * imports all the apps and simulation tools for the
        #  current scenario
        import_str = self._setup_import
        states = []
        for example in annotated_queries.correct + annotated_queries.edited:
            state_info = {
                "query": example.query,
                # at this stage the query has been written to the corpus,
                # we use it's 'final' ID for the database files
                "query_id": self._session_manager.get_query_id(example.query),
                "initial_states": [],
                "final_states": [],
            }
            execution_program = (
                example.edited_program if example.contains_edits else example.program
            )
            runtime_state_programs = example.state_generation_programs
            for setup_program in runtime_state_programs:
                context = ExecutionContext()
                with new_context(context):
                    response = self._execution_environment.execute(
                        program=setup_program, imports=import_str
                    )
                    assert (
                        response.tool_call_exception is None
                    ), f"Setup execution failed with {response.tool_call_exception}"
                    state_info["initial_states"].append(
                        {"dbs": deepcopy(context.to_dict())}
                    )
                    response = self._execution_environment.execute(
                        program=execution_program, imports=import_str
                    )
                    try:
                        assert (
                            response.tool_call_exception is None
                        ), f"Query execution failed with {response.tool_call_exception}"
                    except AssertionError:
                        assert_requires_input_error(response.tool_call_exception)
                    state_info["final_states"].append(
                        {"dbs": deepcopy(context.to_dict())}
                    )
            states.append(EnvironmentState(**state_info))
        self._session_manager.stage_databases(states)

    @property
    def _execution_import(self) -> str:
        """* imports of all the content of the implementations
        for the apps in the current scenario."""
        imports = get_imports(
            self._scenario, import_simulation_tools=False, executable=True
        )
        return "".join(imports)

    @property
    def _setup_import(self) -> str:
        """* imports of all the content of the implementations
        for the apps in the current scenario and the simulation
        tools"""
        imports = get_imports(
            self._scenario, import_simulation_tools=True, executable=True
        )
        return "".join(imports)

    def _maybe_generate_evaluation_assets(
        self, annotated_queries: AnnotatedDatapoints, messages: MessageList
    ):
        """Generate code to setup the runtime environment and evaluate that
        the executed program fulfils the user intent.

         Parameters
         ----------
         messages
            The current chat history.
         annotated_queries
            The queries annotated with execution plans. This function populates
             `state_generation_programs`  and possibly `evaluation_programs` for
             the datapoints.
        """

        # generate and curate additional code which initialises the databases
        #  as required by the user query
        self._maybe_generate_environment_setup_code(messages, annotated_queries)
        # and code that checks the user request was correctly executed
        self._maybe_generate_execution_test_code(messages, annotated_queries)

    def _prompt_user_for_evaluation_tool_selection(
        self, scenario: Scenario
    ) -> Scenario:
        """Prompts the data curator to select the tools which the LLM needs for
        testing the execution of the current query, reloading the relevant modules
        if the data curator implements a new testing tool."""

        def validate_response(user_response: str):
            assert all("::" in s for s in user_response.split(","))

        if scenario.evaluation_tools is None:
            return scenario
        self._console.print(
            EVALUATION_TOOLS_IMPLEMENTATION,
            style="info",
        )
        default_tools = parse_tools(scenario.evaluation_tools)
        self._console.print(
            display_simulation_tools(default_tools, EVALUATION_TOOLS_PATH)
        )
        while True:
            # noqa
            user_response = Prompt.ask(
                EVALUATION_TOOLS_NOTIFICATION, default="no"
            ).strip()
            if user_response in {"no"}:
                self._selected_evaluation_tools = scenario.evaluation_tools
                return scenario
            try:
                validate_response(user_response)
            except AssertionError:
                self._console.print("Invalid input. Please try again.", style="danger")
                user_response = Prompt.ask(
                    EVALUATION_TOOLS_NOTIFICATION, default="no"
                ).strip()
            user_configured_tools = [t.strip() for t in user_response.split(",")]
            self._selected_evaluation_tools = user_configured_tools
            self.reload_modules(
                user_configured_tools,
                docs_tool_path=EVALUATION_TOOLS_PATH,
                tool_impl_path=EVALUATION_TOOLS_IMPLEMENTATIONS_PATH,
            )
            scenario = deepcopy(scenario)
            scenario.evaluation_tools = user_configured_tools
            return scenario
