#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import random
from importlib import resources
from pathlib import Path
from typing import cast

import hydra
import omegaconf
from omegaconf import DictConfig
from rich.prompt import Prompt

from aspera.constants import QUERY_FILE_EXTENSION, QUERY_TO_QUERY_ID_JSON
from aspera.dataset_schema import DataPoint, EditedDataPoint
from aspera.interactive.display import (
    display_edits_multitable,
    display_programs,
    display_queries,
)
from aspera.readers import load_json, read_all_shards_flat
from aspera.utils import generate_batches

USER_MESSAGE = "[bold green]Continue?[/bold green]"  # noqa


def _get_page_size(cfg: DictConfig, default: int = 3) -> int:
    try:
        return cfg.page_size
    except omegaconf.MissingMandatoryValue:
        return default


def _set_seed(cfg):
    if seed := cfg.seed is not None:
        random.seed(seed)


@hydra.main(
    config_name="visualisation",
    config_path="pkg://aspera.configs.endpoints",
)
def queries(cfg: DictConfig):
    _set_seed(cfg)
    all_queries = cast(
        list[DataPoint],
        [
            DataPoint(**e)
            for e in read_all_shards_flat(
                cfg.queries_dir, extension=QUERY_FILE_EXTENSION
            )
        ],
    )
    random.shuffle(all_queries)
    page_size = _get_page_size(cfg)
    for batch in generate_batches(all_queries, page_size):
        display_programs(batch, show_syntax_errors=False)
        should_continue = Prompt.ask(USER_MESSAGE, default="yes")
        if should_continue.lower() in ["no", "n"]:
            break


@hydra.main(
    config_name="visualisation.yaml",
    config_path="pkg://aspera.configs.endpoints",
)
def edits(cfg: DictConfig):
    _set_seed(cfg)
    all_edits = cast(
        list[EditedDataPoint],
        [
            EditedDataPoint(**e)
            for e in read_all_shards_flat(cfg.edits_dir, extension=QUERY_FILE_EXTENSION)
        ],
    )

    random.shuffle(all_edits)
    page_size = _get_page_size(cfg, default=1)
    for batch in generate_batches(all_edits, page_size):
        display_edits_multitable(batch)
        should_continue = Prompt.ask(USER_MESSAGE, default="yes", choices=["yes", "no"])
        if should_continue.lower() in ["no", "n"]:
            break


@hydra.main(
    config_name="visualisation.yaml",
    config_path="pkg://aspera.configs.endpoints",
)
def utterances(cfg: DictConfig):
    _set_seed(cfg)
    index_pth = Path(cfg.queries_dir) / QUERY_TO_QUERY_ID_JSON
    queries_idx = load_json(index_pth)
    queries = list(queries_idx.keys())
    ids_ = list(queries_idx.values())
    random.shuffle(queries)
    page_size = _get_page_size(cfg, default=15)
    q_it = generate_batches(queries, page_size)
    id_it = generate_batches(ids_, page_size)
    for batch_ids, batch in zip(id_it, q_it):
        display_queries(batch, ids=batch_ids)
        should_continue = Prompt.ask(USER_MESSAGE, default="yes", choices=["yes", "no"])
        if should_continue.lower() in ["no", "n"]:
            break
