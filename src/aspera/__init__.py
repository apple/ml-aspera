#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import sys
from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "ml-ASPERA"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError


def _resolve_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _parent(path: str) -> Path:
    return Path(path).parent


def _subfield(node: DictConfig, field: str):
    return node[field]


OmegaConf.register_new_resolver("subfield", _subfield)
OmegaConf.register_new_resolver("root", lambda path: f"{_resolve_root() / path}")
OmegaConf.register_new_resolver("parent", lambda path: f"{_parent(path)}")

sys.path.append(str(_resolve_root()))
