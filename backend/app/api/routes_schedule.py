"""Scoring for hand-edited timetables.

Lets the UI show the cost of a drag-and-drop edit instantly, using the same evaluator
the optimizers use - the frontend never reimplements the fitness function.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..data import load_dataset
from ..models import ScheduleEvaluateRequest
from ..optimization import Problem, evaluate
from ..optimization.fuzzy import profile

router = APIRouter(prefix="/api", tags=["schedule"])


@router.post("/schedule/evaluate")
def evaluate_schedule(request: ScheduleEvaluateRequest) -> dict:
    try:
        problem = Problem(load_dataset(request.dataset_id))
    except KeyError:
        raise HTTPException(404, "Unknown dataset")

    schedule = {sid: slot.model_dump() for sid, slot in request.schedule.items()}
    expected = {session.id for session in problem.sessions}
    unknown = sorted(set(schedule) - expected)
    if unknown:
        raise HTTPException(422, f"Unknown session ids: {', '.join(unknown[:5])}")
    missing = sorted(expected - set(schedule))
    if missing:
        # Scoring a partial timetable would mean inventing placements for the rest and
        # reporting the resulting clashes as if the caller had caused them.
        raise HTTPException(422, f"Schedule is missing {len(missing)} session(s): "
                                 f"{', '.join(missing[:5])}")

    candidate = problem.from_schedule(schedule)
    score = evaluate(problem, candidate, request.weights)
    return {"score": score.as_dict(), "schedule": problem.to_schedule(candidate)}


@router.get("/fuzzy/profile")
def fuzzy_profile() -> dict:
    """Membership curves and the rule base, so the UI can show why a score was given."""
    return profile()
