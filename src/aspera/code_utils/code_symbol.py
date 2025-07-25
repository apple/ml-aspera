#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import inspect
from typing import Any

from pydantic import BaseModel


class CodeSymbol(BaseModel):
    obj_name: str
    module_name: str
    symbol_ref: Any

    @property
    def import_path(self) -> str:
        return f"{self.module_name}.{self.obj_name}"

    @property
    def line_no(self) -> int:
        try:
            _, lineno = inspect.getsourcelines(self.symbol_ref)
            return lineno
        except (TypeError, OSError):
            # For dynamically defined stuff like Enums or type aliases, we can't get the source
            # But as a general rule we can assume they're defined at the top, so put them first
            return 0


def dedup_and_sort_symbols(symbols: list[CodeSymbol]) -> list[CodeSymbol]:
    symbols_dedup = []
    for symb in symbols:
        if symb.obj_name not in [s.obj_name for s in symbols_dedup]:
            symbols_dedup.append(symb)
    symbols_dedup.sort(key=lambda x: x.line_no)
    return symbols_dedup
