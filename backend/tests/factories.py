"""Builders for tiny, purpose-built datasets.

Each constraint test wants a dataset where exactly one constraint can fire, so the
assertion is about that constraint and nothing else.
"""
from __future__ import annotations

from app.models import Dataset
from app.optimization import Assignment, Problem

BASE = {
    "days": ["Mon", "Tue"],
    "periods": ["09:00", "10:00", "11:00"],
    "rooms": [
        {"id": "R1", "capacity": 50, "type": "lecture"},
        {"id": "R2", "capacity": 50, "type": "lecture"},
        {"id": "L1", "capacity": 50, "type": "lab"},
    ],
    "faculty": [{"id": "F1", "name": "Dr One"}, {"id": "F2", "name": "Dr Two"}],
    "groups": [{"id": "G1", "size": 30}, {"id": "G2", "size": 30}],
    "courses": [{
        "id": "C1", "name": "Course One", "faculty_id": "F1", "group_ids": ["G1"],
        "sessions_per_week": 1, "room_type": "lecture",
    }],
}

LAB_COURSE = {
    "id": "C1", "name": "Lab Course", "faculty_id": "F1", "group_ids": ["G1"],
    "sessions_per_week": 1, "room_type": "lab",
}


def course(cid: str, *, faculty: str = "F1", groups: tuple[str, ...] = ("G1",),
           sessions: int = 1, room_type: str = "lecture", **extra) -> dict:
    return {"id": cid, "name": f"Course {cid}", "faculty_id": faculty,
            "group_ids": list(groups), "sessions_per_week": sessions,
            "room_type": room_type, **extra}


def build(**overrides) -> Problem:
    """A Problem from BASE with the given top-level keys replaced."""
    return Problem(Dataset.model_validate({**BASE, **overrides}))


def place(*slots: tuple[int, int, str]) -> list[Assignment]:
    return [Assignment(day, period, room) for day, period, room in slots]
