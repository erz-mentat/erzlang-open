from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CalibrationPoint:
    raw_score: float
    probability: float


@dataclass(frozen=True)
class PiecewiseLinearCalibration:
    points: tuple[CalibrationPoint, ...]


def map_raw_score_to_probability(
    raw_score: float,
    calibration: PiecewiseLinearCalibration | Mapping[str, Any] | Sequence[Any],
) -> float:
    """Deterministically map a raw score to a calibrated probability (piecewise-linear).

    v0 behavior:
    - `raw_score` is expected in [0.0, 1.0]
    - calibration points are sorted by `raw_score`
    - values below/above calibration range are clamped to edge probabilities
    - between two points, linear interpolation is used
    """

    normalized_raw_score = _coerce_unit_interval_number(raw_score, "raw_score")
    points = _normalize_points(calibration)

    first = points[0]
    if normalized_raw_score <= first.raw_score:
        return first.probability

    last = points[-1]
    if normalized_raw_score >= last.raw_score:
        return last.probability

    for left, right in zip(points, points[1:]):
        if normalized_raw_score == left.raw_score:
            return left.probability

        if normalized_raw_score < right.raw_score:
            interval = right.raw_score - left.raw_score
            ratio = (normalized_raw_score - left.raw_score) / interval
            probability = left.probability + ratio * (right.probability - left.probability)
            return probability

    return last.probability


def _normalize_points(
    calibration: PiecewiseLinearCalibration | Mapping[str, Any] | Sequence[Any],
) -> tuple[CalibrationPoint, ...]:
    if isinstance(calibration, PiecewiseLinearCalibration):
        raw_points: Sequence[Any] = calibration.points
    elif isinstance(calibration, Mapping):
        raw_points = calibration.get("points")
        if raw_points is None:
            raise ValueError("calibration mapping must contain 'points'")
    else:
        raw_points = calibration

    if not isinstance(raw_points, Sequence) or isinstance(raw_points, (str, bytes, bytearray)):
        raise TypeError("calibration points must be a sequence")

    normalized: list[CalibrationPoint] = []
    for index, item in enumerate(raw_points):
        normalized.append(_normalize_point(item, index=index))

    if len(normalized) < 2:
        raise ValueError("calibration must contain at least two points")

    normalized.sort(key=lambda point: point.raw_score)

    for prev, cur in zip(normalized, normalized[1:]):
        if prev.raw_score == cur.raw_score:
            raise ValueError("calibration points must have unique raw_score values")

    return tuple(normalized)


def _normalize_point(item: Any, *, index: int) -> CalibrationPoint:
    if isinstance(item, CalibrationPoint):
        raw = item.raw_score
        probability = item.probability
    elif isinstance(item, Mapping):
        allowed = {"raw_score", "probability"}
        unknown = set(item.keys()) - allowed
        if unknown:
            unknown_keys = ", ".join(sorted(str(key) for key in unknown))
            raise TypeError(f"calibration point[{index}] has unknown field(s): {unknown_keys}")

        if "raw_score" not in item or "probability" not in item:
            raise TypeError(f"calibration point[{index}] must include raw_score and probability")

        raw = item["raw_score"]
        probability = item["probability"]
    elif isinstance(item, (tuple, list)) and len(item) == 2:
        raw, probability = item
    else:
        raise TypeError(
            "calibration point must be CalibrationPoint, mapping, or (raw_score, probability) tuple"
        )

    return CalibrationPoint(
        raw_score=_coerce_unit_interval_number(raw, f"calibration point[{index}].raw_score"),
        probability=_coerce_unit_interval_number(probability, f"calibration point[{index}].probability"),
    )


def _coerce_unit_interval_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")

    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be in [0.0, 1.0]")

    return normalized
