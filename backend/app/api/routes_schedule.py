"""Scoring for hand-edited timetables.

Lets the UI show the cost of a drag-and-drop edit instantly, using the same evaluator
the optimizers use - the frontend never reimplements the fitness function.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..data import load_dataset
from ..models import ScheduleEvaluateRequest
from ..optimization import Problem, evaluate

router = APIRouter(prefix="/api", tags=["schedule"])


@router.post("/schedule/evaluate")
def evaluate_schedule(request: ScheduleEvaluateRequest) -> dict:
    try:
        problem = Problem(load_dataset(request.dataset_id))
    except KeyError:
        raise HTTPException(404, "Unknown dataset")

    schedule = {sid: slot.model_dump() for sid, slot in request.schedule.items()}
    unknown = sorted(set(schedule) - {session.id for session in problem.sessions})
    if unknown:
        raise HTTPException(422, f"Unknown session ids: {', '.join(unknown[:5])}")

    candidate = problem.from_schedule(schedule)
    score = evaluate(problem, candidate, request.weights)
    return {"score": score.as_dict(), "schedule": problem.to_schedule(candidate)}
