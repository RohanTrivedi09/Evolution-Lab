"""Optimization runs and algorithm comparisons."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import RunRequest
from ..services.run_manager import manager

router = APIRouter(prefix="/api", tags=["runs"])


def _run_or_404(run_id: str) -> dict:
    try:
        return manager.get_run(run_id)
    except KeyError:
        raise HTTPException(404, "Unknown run")


@router.post("/runs")
def create_run(request: RunRequest) -> dict:
    try:
        record = manager.create_run(request)
    except KeyError:
        raise HTTPException(404, "Unknown dataset")
    return {"run_id": record["run_id"], "status": record["status"],
            "max_evaluations": record["max_evaluations"]}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return _run_or_404(run_id)


@router.get("/runs/{run_id}/history")
def history(run_id: str) -> dict:
    return {"history": _run_or_404(run_id).get("result", {}).get("history", [])}


@router.get("/runs/{run_id}/trajectory")
def trajectory(run_id: str) -> dict:
    return {"trajectory": _run_or_404(run_id).get("result", {}).get("trajectory", [])}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str) -> dict:
    _run_or_404(run_id)
    return {"status": manager.cancel_run(run_id)}


@router.get("/runs/{run_id}/export")
def export_run(run_id: str) -> dict:
    return _run_or_404(run_id)


@router.post("/comparisons")
def create_comparison(request: RunRequest) -> dict:
    try:
        return manager.create_comparison(request)
    except KeyError:
        raise HTTPException(404, "Unknown dataset")


@router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: str) -> dict:
    try:
        return manager.get_comparison(comparison_id)
    except KeyError:
        raise HTTPException(404, "Unknown comparison")
