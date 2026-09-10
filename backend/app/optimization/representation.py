"""Timetable problem representation: sessions, assignments, and the search domain."""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..models import Dataset


@dataclass(frozen=True)
class Session:
    """One concrete weekly meeting of a course."""

    id: str
    course_id: str
    name: str
    faculty_id: str
    group_ids: tuple[str, ...]
    room_type: str
    occurrence: int


@dataclass
class Assignment:
    """Where a session is placed: a day/period slot and a room."""

    day: int
    period: int
    room: str

    def copy(self) -> "Assignment":
        return Assignment(self.day, self.period, self.room)

    def key(self) -> tuple[int, int, str]:
        return (self.day, self.period, self.room)


Candidate = list[Assignment]


class Problem:
    """Static, immutable view of a dataset plus the candidate domain it defines."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.rooms = {room.id: room for room in dataset.rooms}
        self.faculty = {member.id: member for member in dataset.faculty}
        self.groups = {group.id: group for group in dataset.groups}
        self.room_ids = [room.id for room in dataset.rooms]
        self.day_count = len(dataset.days)
        self.period_count = len(dataset.periods)

        self.sessions = [
            Session(f"{course.id}-{n}", course.id, course.name, course.faculty_id,
                    tuple(course.group_ids), course.room_type, n)
            for course in dataset.courses
            for n in range(1, course.sessions_per_week + 1)
        ]

        self.sessions_by_course: dict[str, list[int]] = {}
        for index, session in enumerate(self.sessions):
            self.sessions_by_course.setdefault(session.course_id, []).append(index)

        self.course_preferences = {
            course.id: {
                (dataset.days.index(p.day), dataset.periods.index(p.period))
                for p in course.preferred_periods
                if p.day in dataset.days and p.period in dataset.periods
            }
            for course in dataset.courses
        }
        self.faculty_undesirable = {
            member.id: {
                (dataset.days.index(p.day), dataset.periods.index(p.period))
                for p in member.undesirable
                if p.day in dataset.days and p.period in dataset.periods
            }
            for member in dataset.faculty
        }

    @property
    def slot_count(self) -> int:
        """Number of distinct (day, period, room) placements one session may take."""
        return self.day_count * self.period_count * len(self.room_ids)

    def random_assignment(self, rng: random.Random) -> Assignment:
        return Assignment(rng.randrange(self.day_count),
                          rng.randrange(self.period_count),
                          rng.choice(self.room_ids))

    def random_candidate(self, rng: random.Random) -> Candidate:
        return [self.random_assignment(rng) for _ in self.sessions]

    def in_domain(self, assignment: Assignment) -> bool:
        return (0 <= assignment.day < self.day_count
                and 0 <= assignment.period < self.period_count
                and assignment.room in self.rooms)

    def to_schedule(self, candidate: Candidate) -> dict[str, dict]:
        """Render a candidate as the API's day/period/room schedule map."""
        return {
            session.id: {
                "day": self.dataset.days[assignment.day],
                "period": self.dataset.periods[assignment.period],
                "room_id": assignment.room,
            }
            for session, assignment in zip(self.sessions, candidate)
            if self.in_domain(assignment)
        }

    def from_schedule(self, schedule: dict[str, dict]) -> Candidate:
        """Rebuild a candidate from a schedule map, for user-edited timetables.

        Sessions missing from the map keep a deterministic fallback placement so a
        partial edit never shortens the candidate.
        """
        days = {name: index for index, name in enumerate(self.dataset.days)}
        periods = {name: index for index, name in enumerate(self.dataset.periods)}
        candidate: Candidate = []
        for session in self.sessions:
            slot = schedule.get(session.id)
            if not slot:
                candidate.append(Assignment(0, 0, self.room_ids[0]))
                continue
            candidate.append(Assignment(days.get(slot.get("day"), 0),
                                        periods.get(slot.get("period"), 0),
                                        slot.get("room_id", self.room_ids[0])))
        return candidate

    @staticmethod
    def distance(left: Candidate, right: Candidate) -> int:
        """Hamming distance over placements, used for diversity and trajectory plots."""
        return sum(1 for a, b in zip(left, right) if a.key() != b.key())

    @staticmethod
    def fingerprint(candidate: Candidate) -> tuple:
        return tuple(a.key() for a in candidate)
