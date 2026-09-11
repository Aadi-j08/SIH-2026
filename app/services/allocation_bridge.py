"""
Bridge between SQLite rows and the existing fair allocation engine.

This is the only new module that touches app/services/allocation.py and
app/schemas.py. It never modifies them: it converts rows into the schemas
recommend_workers() expects, calls it, and normalises what comes back.

If a booking column is spelled differently from a ServiceRequest field,
add the pair to SYNONYMS below.
"""
from __future__ import annotations

import collections.abc
import dataclasses
import inspect
import json
import typing
from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas import ServiceRequest
from app.services.allocation import recommend_workers

# Groups of names that mean the same thing across tables and schemas.
SYNONYMS: tuple[tuple[str, ...], ...] = (
    ("trade", "service_type", "skill", "service", "category", "required_skill"),
    ("latitude", "lat"),
    ("longitude", "lng", "lon", "long"),
    ("scheduled_for", "scheduled_time", "scheduled_at", "time_slot", "slot", "preferred_time"),
    ("location", "area", "locality", "micro_location", "address"),
)
_REQUEST_EXTRA = {"booking_id": ("id",), "request_id": ("id",)}
_WORKER_EXTRA = {"worker_id": ("id",), "id": ("worker_id",)}

_REQUEST_PARAM_NAMES = {"request", "service_request", "req", "booking_request"}
_WORKER_PARAM_NAMES = {"workers", "candidates", "worker_pool", "available_workers"}
_SEQUENCE_ORIGINS = {
    list, tuple, set, frozenset,
    collections.abc.Sequence, collections.abc.Iterable, collections.abc.Collection,
}


class AllocationBridgeError(RuntimeError):
    """The booking or worker data could not be matched to the allocation engine's contract."""


@dataclasses.dataclass(frozen=True)
class RankedWorker:
    worker_id: int
    score: float
    score_breakdown: Any
    explanation: str


_MISSING = object()


def _coerce(value: Any) -> Any:
    """Decode JSON text stored in SQLite (e.g. skill lists) so Pydantic can validate it."""
    if isinstance(value, str) and value[:1] in ("[", "{"):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _lookup(field: str, alias: str | None, row: dict, extra: dict[str, tuple[str, ...]]) -> Any:
    for name in (field, alias):
        if name and name in row:
            return row[name]
    for group in SYNONYMS:
        if field in group:
            for name in group:
                if name in row:
                    return row[name]
    for name in extra.get(field, ()):
        if name in row:
            return row[name]
    return _MISSING


def _build(model_cls: type, row: dict, extra: dict[str, tuple[str, ...]]) -> Any:
    if isinstance(model_cls, type) and issubclass(model_cls, BaseModel):
        data = {}
        for name, info in model_cls.model_fields.items():
            value = _lookup(name, info.alias, row, extra)
            if value is not _MISSING:
                data[info.alias or name] = _coerce(value)
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            raise AllocationBridgeError(
                f"Could not build {model_cls.__name__} from row with columns "
                f"{sorted(row)}: {exc.errors(include_url=False)}"
            ) from exc
    if dataclasses.is_dataclass(model_cls):
        data = {}
        for f in dataclasses.fields(model_cls):
            value = _lookup(f.name, None, row, extra)
            if value is not _MISSING:
                data[f.name] = _coerce(value)
        try:
            return model_cls(**data)
        except TypeError as exc:
            raise AllocationBridgeError(f"Could not build {model_cls.__name__}: {exc}") from exc
    return {key: _coerce(value) for key, value in row.items()}


def build_service_request(booking: dict) -> ServiceRequest:
    return _build(ServiceRequest, booking, _REQUEST_EXTRA)


def _element_type(annotation: Any) -> Any:
    if typing.get_origin(annotation) in _SEQUENCE_ORIGINS:
        args = typing.get_args(annotation)
        return args[0] if args else None
    return None


def _is_request_param(name: str, annotation: Any) -> bool:
    if isinstance(annotation, type) and issubclass(annotation, ServiceRequest):
        return True
    return name in _REQUEST_PARAM_NAMES


def _is_workers_param(name: str, annotation: Any) -> bool:
    return name in _WORKER_PARAM_NAMES or _element_type(annotation) is not None


def _call_engine(request: ServiceRequest, worker_rows: list[dict]) -> Any:
    signature = inspect.signature(recommend_workers)
    try:
        hints = typing.get_type_hints(recommend_workers)
    except Exception:  # unresolvable forward references: fall back to raw annotations
        hints = {}

    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = hints.get(name, param.annotation)
        if _is_request_param(name, annotation):
            value = request
        elif _is_workers_param(name, annotation):
            element = _element_type(annotation)
            value = [_build(element, row, _WORKER_EXTRA) for row in worker_rows]
        elif param.default is not inspect.Parameter.empty:
            continue  # optional tuning parameter such as top_k: keep the engine's default
        else:
            raise AllocationBridgeError(
                f"recommend_workers() requires '{name}', which the bridge doesn't know how to supply."
            )
        if param.kind is param.POSITIONAL_ONLY:
            args.append(value)
        else:
            kwargs[name] = value
    return recommend_workers(*args, **kwargs)


def _as_dict(item: Any) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump()
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return dataclasses.asdict(item)
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "_asdict"):
        return item._asdict()
    raise AllocationBridgeError(f"Unrecognised recommendation type: {type(item).__name__}")


def _first(data: dict, *keys: str) -> Any:
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


def _normalise(result: Any) -> list[RankedWorker]:
    if isinstance(result, BaseModel) and hasattr(result, "recommendations"):
        items = result.recommendations
    elif isinstance(result, dict) and "recommendations" in result:
        items = result["recommendations"]
    elif isinstance(result, (list, tuple)):
        items = result
    elif result is None:
        items = []
    else:
        items = [result]

    ranked: list[RankedWorker] = []
    for item in items:
        data = _as_dict(item)
        nested = data.get("worker") if isinstance(data.get("worker"), dict) else {}
        worker_id = _first(data, "worker_id") or _first(nested, "id", "worker_id") or _first(data, "id")
        score = _first(data, "score", "total_score", "allocation_score", "final_score")
        if worker_id is None or score is None:
            raise AllocationBridgeError(
                f"Recommendation is missing a worker id or score. Keys seen: {sorted(data)}"
            )
        breakdown = _first(data, "score_breakdown", "breakdown", "components", "factors", "scores") or {}
        explanation = _first(data, "explanation", "reason", "reasons", "rationale") or ""
        if isinstance(explanation, (list, tuple)):
            explanation = "; ".join(str(part) for part in explanation)
        ranked.append(RankedWorker(int(worker_id), float(score), breakdown, str(explanation)))
    return ranked


def rank_workers(booking: dict, worker_rows: list[dict]) -> list[RankedWorker]:
    """Run the existing engine for a booking and return its ranking, best first."""
    ranked = _normalise(_call_engine(build_service_request(booking), worker_rows))
    return sorted(ranked, key=lambda r: r.score, reverse=True)


def top_recommendation(booking: dict, worker_rows: list[dict]) -> RankedWorker | None:
    ranked = rank_workers(booking, worker_rows)
    return ranked[0] if ranked else None
