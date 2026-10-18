"""Dataset discovery and validation."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from ..data import list_datasets, load_dataset, register_dataset
from ..models import Dataset
from ..optimization import Problem

router = APIRouter(prefix="/api", tags=["datasets"])


@router.get("/datasets")
def datasets() -> dict:
    return {"datasets": list_datasets()}


def _parse(payload: dict) -> tuple[Dataset | None, list[str]]:
    """Validate a raw body, turning Pydantic's machine-shaped errors into readable ones."""
    raw = payload.get("dataset", payload)
    if not isinstance(raw, dict):
        return None, ['Body must be a JSON object, or {"dataset": {...}}']
    try:
        return Dataset.model_validate(raw), []
    except ValidationError as exc:
        return None, [f"{'.'.join(str(part) for part in item['loc']) or 'dataset'}: {item['msg']}"
                      for item in exc.errors()]


@router.post("/datasets")
def upload_dataset(payload: dict = Body(...)) -> dict:
    """Accept a pasted dataset for this session and return the id to run it under."""
    parsed, errors = _parse(payload)
    if parsed is None:
        raise HTTPException(422, {"valid": False, "errors": errors})
    dataset_id = register_dataset(parsed)
    problem = Problem(parsed)
    return {"dataset_id": dataset_id, "name": parsed.name or dataset_id,
            "sessions": len(problem.sessions), "slots_per_session": problem.slot_count}


@router.get("/datasets/{dataset_id}")
def dataset(dataset_id: str) -> dict:
    try:
        return load_dataset(dataset_id).model_dump()
    except KeyError:
        raise HTTPException(404, "Unknown dataset")


@router.post("/datasets/validate")
def validate(payload: dict = Body(...)) -> dict:
    """Validate a pasted or uploaded dataset and report readable errors.

    Taking a raw body rather than a typed model is deliberate: it lets us turn Pydantic's
    machine-shaped errors into field-level messages a user can act on, instead of the
    framework rejecting the request with a bare 422 before we ever see it.
    """
    parsed, errors = _parse(payload)
    if parsed is None:
        return {"valid": False, "errors": errors}

    problem = Problem(parsed)
    return {
        "valid": True,
        "errors": [],
        "sessions": len(problem.sessions),
        "summary": {
            "days": len(parsed.days), "periods": len(parsed.periods),
            "rooms": len(parsed.rooms), "faculty": len(parsed.faculty),
            "groups": len(parsed.groups), "courses": len(parsed.courses),
            "slots_per_session": problem.slot_count,
        },
    }
