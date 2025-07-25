#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import glob
import json
import logging
import os.path
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import nestedtext as nt
from omegaconf import OmegaConf

from aspera.aliases import Query, QueryIdx, ShardPath
from aspera.code_utils.utils import (
    remove_import_statements,
    remove_module_comments,
)
from aspera.constants import (
    EVALUATION_PROGRAM_FUNCTION_NAME_PREFIX,
    QUERY_FILE_EXTENSION,
    QUERY_ID_TO_SHARD_JSON,
    QUERY_TO_QUERY_ID_JSON,
    RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX,
)
from aspera.dataset_schema import AnnotatedPrograms
from aspera.parser import (
    ExtractFunctionName,
    ProgramParserBasic,
    ProgramStringFinder,
    RemoveEntryPointCode,
)

logger = logging.getLogger(__name__)


class QueryNotFoundError(Exception):
    pass


def load_json(path: str | Path):
    with open(path, "r") as f:
        data = json.load(f)
    return data


def load_nestedtext(opath: Path | str) -> Any:
    """Read the context of a NestedText file."""
    with open(opath, "r") as f:
        data = nt.load(f, top="any")
    return data


_LOADER_MAP = {"json": load_json, "nt": load_nestedtext}


def _get_last_shard(
    dir_: Path, extension: str = QUERY_FILE_EXTENSION, prefix: str = "queries"
) -> Path | None:
    n_shards = count_shards(str(dir_), extension=extension)
    if n_shards == 0:
        return
    return dir_ / f"{prefix}_{n_shards:03}.{extension}"


def _get_shard_idx(dir_: Path) -> int:
    return int(dir_.stem.split("_")[-1])


def _read_shard_content(
    shard: str | Path, extension: str = "json"
) -> list[dict[str, Any]]:
    """Reads the content of a shard."""
    try:
        loader = _LOADER_MAP[extension]
    except KeyError:
        logger.error(f"Undefined loader for extension {extension}")
        return []
    content = []
    data = loader(shard)
    if isinstance(data, list):
        content.extend(data)
    else:
        content.append(data)
    return content


def _shard_iterator(
    dir_: Path | str, extension: str = "json", prefix: str = "queries"
) -> Iterator[str]:
    pattern = os.path.join(str(dir_), f"{prefix}*.{extension}")
    shards = list(glob.glob(pattern))
    for shard in shards:
        yield shard


def read_all_shards_flat(
    dir_: Path | str, extension: str = "json", prefix: str = "queries"
) -> list:
    """Concatenate the content of all shards in `dir_` in a single list."""
    content = []
    for shard in _shard_iterator(dir_, extension, prefix):
        content += _read_shard_content(shard, extension)
    if not content:
        logger.info(f"No {extension} shards found in {dir_}")
    return content


def read_all_shards_lookup(
    dir_: Path | str, extension: str = "json", prefix: str = "queries"
) -> dict[ShardPath, list[dict[str, Any]]]:
    """Load the data as a lookup from shard name to the data contained in that shard."""
    content = {}
    for shard in _shard_iterator(dir_, extension, prefix):
        content[shard] = _read_shard_content(shard, extension)
    if not content:
        logger.info(f"No {extension} shards found in {dir_}")
    return content


def count_shards(
    path: str, extension: str = "json", shard_prefix: str = "queries"
) -> int:
    shards = [
        f
        for f in glob.glob(f"{path}/*.{extension}")
        if Path(f).name.startswith(shard_prefix)
    ]
    return len(shards)


class ParseError(Exception):
    pass


def parse_plans_and_evaluation_assets(
    query_id: str, code_dir: Path
) -> AnnotatedPrograms:
    """Parse the python modules containing the gold plans, runtime setup programs
    and evaluation programs"""
    module_name = f"query_{query_id}.py"
    module_path = code_dir / module_name
    parser = ProgramParserBasic(
        preprocessor=ProgramStringFinder(start_seq="", end_seq="")
    )
    fcn_name_parser = ExtractFunctionName()
    with open(module_path, "r") as f:
        code = f.read()
    code = RemoveEntryPointCode()(code)
    code = remove_import_statements(code, package_name=None).strip("\n ")
    code = remove_module_comments(code).strip("\n ")
    programs = parser.parse(code)
    function_names = [fcn_name_parser(p) for p in programs if p]
    data = {"plan": None, "state": [], "eval": []}
    for p, fcn_name in zip(programs, function_names):
        if fcn_name.startswith(RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX):
            data["state"].append(p)
        elif fcn_name.startswith(EVALUATION_PROGRAM_FUNCTION_NAME_PREFIX):
            data["eval"].append(p)
        else:
            if data["plan"] is None:
                data["plan"] = p
            else:
                raise ParseError(
                    f"More than one plan found for {query_id}, this is not expected!"
                )
    assert all((data["state"], data["eval"]))
    return AnnotatedPrograms(**data)


def find_query_text(plans_index: str | Path, query_id: str) -> str:
    """Look up `query_id` in the plans index and retrieve the query text
    corresponding to it."""
    query_idx: dict[Query, list[QueryIdx]] = load_json(plans_index)
    query_text = None
    for query, id_ in query_idx.items():
        assert len(id_) == 1
        if query_id == id_[0]:
            query_text = query
            break
    assert query_text is not None, f"Could not find {query_id}"
    return query_text


def get_query_id(query: Query, query_idx_pth: str | Path) -> QueryIdx:
    index: dict[Query, list[QueryIdx]] = load_json(query_idx_pth)
    for q, query_id_lst in index.items():
        if q == query:
            assert len(query_id_lst) == 1, f"Query {q} had multiple IDs {query_id_lst}"
            query_idx = query_id_lst[0]
            break
    else:
        raise ValueError(f"Could not find query {query} in index {query_idx_pth}")
    return query_idx


def load_shard(
    query: Query, query_idx_pth: str | Path
) -> tuple[list[dict[str, Any]], Path]:
    """Load the shard where a given query is stored.

    Parameters
    ----------
    query
        The text of the query which is to be searched in the corpus.
    query_idx_pth
        The path to the index file for the corpus.
    """
    query_idx = get_query_id(query, query_idx_pth)
    shard_dir = query_idx_pth.parent
    shard_idx_path = Path(shard_dir) / QUERY_ID_TO_SHARD_JSON
    shard_lookup = load_json(shard_idx_path)
    shards = shard_lookup[query_idx]
    assert len(shards) == 1, "Not expecting the same query to be in multiple shards"
    shard_path = Path(shard_dir) / shards[0]
    data = load_nestedtext(shard_path)
    return data, shard_path


def get_example(query: Query, data: list[dict[str, Any]]) -> dict[str, Any]:
    examples = [e for e in data if e["query"] == query]
    if not examples:
        raise ValueError(f"Could not find {query} in data")
    if len(examples) > 1:
        raise ValueError(
            f"Multiple examples found for query: {query}, "
            "this is not expected unless you're looking at edits"
        )
    return examples[0]


def load_example(query_id: QueryIdx, index_pth: Path) -> dict[str, Any]:
    """Loads an example from the corpus.

    Parameters
    -----------
    query_id
        The id of the query.
    index_pth
        The path to the index QUERY_TO_QUERY_ID_JSON file bundled with the data
    """
    query_text = find_query_text(index_pth, query_id)
    examples, _ = load_shard(query_text, index_pth)
    return get_example(query_id, examples)


def query_loader(plans_dir: Path | str) -> list[str]:
    """Loads the queries in the dataset."""
    if isinstance(plans_dir, str):
        plans_dir = Path(plans_dir)
    index_path = plans_dir / QUERY_TO_QUERY_ID_JSON
    if not plans_dir.exists() or not index_path.exists():
        logger.warning("Could not found corpus index, queries could not be loaded")
        return []
    index = cast(dict[str, Any], load_json(index_path))
    return list(index.keys())


OmegaConf.register_new_resolver("query_loader", query_loader)
