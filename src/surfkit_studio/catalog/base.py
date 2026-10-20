"""Technique model: the unit the whole app is built around.

A technique is one analysis a researcher can run (CMC from a tensiometry
curve, counterion binding from conductivity, ...). Each one declares what it
needs (a dataset, parameters, values produced by earlier techniques), which
alternative methods exist and the principle behind each, what it unlocks
next, and how honest its numbers are (the toolkit's own validation tiers).

The science lives in SurfactantKit; a technique only adapts inputs to the
toolkit call and turns the result into values, figures and a conclusion.
Nothing here invents a number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Column:
    key: str
    label: str
    units: list[str]                 # first entry is the canonical unit used internally
    aliases: list[str] = field(default_factory=list)   # header words used for auto-detection
    factors: dict[str, float] = field(default_factory=dict)   # unit -> factor to units[0]; overrides the shared table


@dataclass
class DatasetSpec:
    columns: list[Column]
    min_rows: int
    example: str                     # file name under examples/


@dataclass
class Param:
    key: str
    label: str
    kind: str                        # "float" | "choice" | "text"
    unit: str = ""
    default: Any = None
    choices: list[tuple[str, str]] = field(default_factory=list)   # (value, label)
    help: str = ""
    required: bool = True
    from_session: str | None = None  # prefill from a value an earlier technique produced


@dataclass
class Method:
    key: str
    label: str
    principle: str                   # why this method, in one or two sentences
    when: str                        # when a researcher should prefer it


@dataclass
class Value:
    label: str
    value: float | str | bool | None
    unit: str = ""
    sig: int = 4                     # significant figures for display

    def text(self) -> str:
        v = self.value
        if v is None:
            return "n/a"
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, (int, float)):
            s = f"{v:.{self.sig}g}"
            return f"{s} {self.unit}".strip()
        return f"{v} {self.unit}".strip()


@dataclass
class Figure:
    name: str
    png: bytes
    caption: str


@dataclass
class RunInput:
    data: dict[str, list[float]] | None      # canonical-unit columns
    params: dict[str, Any]
    method: str
    session: dict[str, Any]                  # values provided by earlier runs


@dataclass
class RunResult:
    values: list[Value]
    figures: list[Figure]
    conclusion: list[str]                    # plain-language reading of the result
    warnings: list[str] = field(default_factory=list)
    provides: dict[str, Any] = field(default_factory=dict)   # into the session for derived techniques
    toolkit_calls: list[str] = field(default_factory=list)   # SurfactantKit functions actually called


@dataclass
class Technique:
    id: str
    category: str
    title: str
    level: str                               # "primary" (raw data) | "derived" (earlier results) | "structure" (molecule)
                                             # | "measurement" (a few measured numbers typed in, no curve)
    summary: str
    run: Callable[[RunInput], RunResult]
    dataset: DatasetSpec | None = None
    params: list[Param] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)        # session keys that must exist
    produces: list[str] = field(default_factory=list)        # session keys this technique adds
    tools: list[str] = field(default_factory=list)           # toolkit names, for validation tiers
    citations: list[str] = field(default_factory=list)       # keys into citations.REFERENCES
    unlocks: list[str] = field(default_factory=list)         # technique ids this result enables
    followups: list[str] = field(default_factory=list)       # what the researcher can do next
    keywords: list[str] = field(default_factory=list)        # chat routing hints
