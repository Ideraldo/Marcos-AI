"""Shared shape of the candidate registries.

The metadata lives here, next to the name, instead of inside each engine class:
listing what exists must not import torch, onnxruntime and everything else just
to print a table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

#: How a model relates to Portuguese.
#:   pt    -- trained or fine-tuned on Portuguese only. The specialists.
#:   multi -- multilingual model that happens to support pt.
#: A specialist is usually smaller for the same accuracy, which is the whole
#: argument on a Pi. It also cannot fall back to another language, which is
#: fine for an assistant that only ever hears pt-BR.
LANGS = {"pt": "especializado em portugues", "multi": "multilingue"}


@dataclass(frozen=True)
class Entry:
    factory: Callable[..., Any]
    lang: str  # pt | multi
    kind: str  # local | cloud
    note: str = ""

    @property
    def flag(self) -> str:
        return "[PT]" if self.lang == "pt" else "    "
