"""Repeated-seed experiment endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import ExperimentRequest
from ..services.experiments import manager

router = APIRouter(prefix="/api", tags=["experiments"])


@router.post("/experiments")
def create_experiment(request: ExperimentRequest) -> dict:
    try:
        record = manager.create(request)
    except KeyError:
        raise HTTPException(404, "Unknown dataset")
    return {"experiment_id": record["experiment_id"], "status": record["status"],
            "total_trials": record["total_trials"],
            "max_evaluations": record["max_evaluations"]}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict:
    try:
        return manager.get(experiment_id)
    except KeyError:
        raise HTTPException(404, "Unknown experiment")
