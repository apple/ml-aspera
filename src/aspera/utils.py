#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Generator

from omegaconf import DictConfig, ListConfig, OmegaConf

logger = logging.getLogger(__name__)


def _scenario_name(
    apps: ListConfig, examples: DictConfig, suffix: str | None = None
) -> str:
    """Determines the name for the session_logs subdirectory where raw data is saved."""
    example_str = ""
    if suffix is None:
        for key, val in examples.items():
            example_str += f"{key}_{'_'.join(val)}_"
        return f"apps__{'_'.join(apps)}__examples__{example_str.strip('_')}"
    return f"apps__{'_'.join(apps)}__{suffix}"


def _suffix(debug: bool = False) -> str | None:
    return "debug" if debug else None


def _show_prompt(debug: bool = False) -> bool:
    return True if debug else False


def create_dir(pth: Path | str, suffix: str | None = None):
    if suffix is not None:
        pth = f"{str(pth)}_{suffix}"
    if isinstance(pth, str):
        pth = Path(pth)

    if not pth.exists():
        pth.mkdir(parents=True)

    return str(pth)


def get_commit_hash():
    """Returns the commit hash for the current HEAD."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode()
    except subprocess.CalledProcessError:
        return "Can not get commit hash."


def generate_batches(input_list: list, k: int) -> Generator[list, None, None]:
    for i in range(0, len(input_list), k):
        yield input_list[i : i + k]


def snake_case(camel_str: str) -> str:
    """Convert method name from camel case to PEP8 style.

    Example
    -------
        "FindRestaurant" -> "find_restaurant"
    """

    snake_str = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str)
    snake_str = re.sub(r"(?<=[a-z])(?=\d)", "_", snake_str)
    snake_str = snake_str.lower()
    if not snake_str:
        return camel_str
    return snake_str


OmegaConf.register_new_resolver("scenario_name", _scenario_name)
OmegaConf.register_new_resolver(
    "create_dir", lambda pth, suffix=None: create_dir(pth, suffix)
)
OmegaConf.register_new_resolver("set_suffix", lambda debug: _suffix(debug))
OmegaConf.register_new_resolver("show_prompt", lambda debug: _show_prompt(debug))


def count_nested_dict_values(d: dict) -> dict:
    def _helper(d: dict, count_d: dict):

        for k, v in d.items():
            if isinstance(v, dict):
                _helper(v, count_d[k])
            else:
                count_d[k] = len(v)

    count_d = deepcopy(d)
    _helper(d, count_d)

    return count_d
