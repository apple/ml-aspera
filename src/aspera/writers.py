#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import json
from pathlib import Path
from typing import Any

import nestedtext as nt
from inform import fatal, os_error


def save_json(data: Any, path: str | Path, indent: int = 4):
    with open(path, "w") as f:
        json.dump(data, f, indent=indent)


def save_json_str(data: Any, path: str | Path, indent: int = 4):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=indent))


def save_nestedtext(data: Any, opath: Path):
    """Save data in NestedText format."""

    try:
        with open(opath, "w") as f:
            nt.dump(data, f)
    except nt.NestedTextError as e:
        e.terminate()
    except OSError as e:
        fatal(os_error(e))
