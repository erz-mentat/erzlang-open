from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ref:
    id: str


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Rule:
    id: str
    clauses: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Action:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceStep:
    rule_id: str
    matched_clauses: list[str]
    score: float | None = None
    calibrated_probability: float | None = None
    timestamp: str | int | float | None = None
    seed: str | int | None = None
