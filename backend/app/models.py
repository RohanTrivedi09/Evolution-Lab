from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Unavailable(BaseModel):
    day: str
    period: str


class Room(BaseModel):
    id: str
    capacity: int = Field(gt=0)
    type: str


class Faculty(BaseModel):
    id: str
    name: str
    unavailable: list[Unavailable] = []
    undesirable: list[Unavailable] = []


class Group(BaseModel):
    id: str
    size: int = Field(gt=0)


class PreferredPeriod(BaseModel):
    day: str
    period: str


class Course(BaseModel):
    id: str
    name: str
    faculty_id: str
    group_ids: list[str]
    sessions_per_week: int = Field(ge=1, le=20)
    duration: int = Field(default=1, ge=1)
    room_type: str
    preferred_periods: list[PreferredPeriod] = []


class Dataset(BaseModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    days: list[str] = Field(min_length=1)
    periods: list[str] = Field(min_length=1)
    rooms: list[Room] = Field(min_length=1)
    faculty: list[Faculty] = Field(min_length=1)
    groups: list[Group] = Field(min_length=1)
    courses: list[Course] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "Dataset":
        errors: list[str] = []
        faculty = {item.id for item in self.faculty}
        groups = {item.id for item in self.groups}
        rooms = {item.type for item in self.rooms}
        for course in self.courses:
            if course.faculty_id not in faculty:
                errors.append(f"Course {course.id} references unknown faculty {course.faculty_id}")
            missing = set(course.group_ids) - groups
            if missing:
                errors.append(f"Course {course.id} references unknown groups: {', '.join(sorted(missing))}")
            if course.room_type not in rooms:
                errors.append(f"Course {course.id} requires unavailable room type {course.room_type}")
        if len(set(self.days)) != len(self.days) or len(set(self.periods)) != len(self.periods):
            errors.append("Days and periods must not contain duplicates")
        if errors:
            raise ValueError("; ".join(errors))
        return self


AlgorithmName = Literal["hill_climbing", "simulated_annealing", "genetic_algorithm", "particle_swarm"]


class Weights(BaseModel):
    hard: float = 10000
    soft: float = 100
    gaps: float = 10
    fragmentation: float = 5


class ScheduledSlot(BaseModel):
    day: str
    period: str
    room_id: str


class RunRequest(BaseModel):
    dataset_id: str = "small-college"
    algorithm: AlgorithmName = "hill_climbing"
    seed: int = 42
    parameters: dict[str, float | int] = {}
    weights: Weights = Weights()
    max_evaluations: int | None = Field(default=None, gt=0, le=2_000_000)
    initial_schedule: dict[str, ScheduledSlot] | None = None


class ExperimentRequest(BaseModel):
    """A repeated-seed comparison: every algorithm, every seed, one shared budget."""

    dataset_id: str = "small-college"
    algorithms: list[AlgorithmName] | None = None
    seeds: list[int] | None = None
    seed_count: int = Field(default=5, ge=1, le=30)
    max_evaluations: int = Field(default=2000, gt=0, le=2_000_000)
    parameters: dict[str, float | int] = {}
    weights: Weights = Weights()

    def resolved_seeds(self) -> list[int]:
        return self.seeds if self.seeds else list(range(1, self.seed_count + 1))


class ScheduleEvaluateRequest(BaseModel):
    """Score a hand-edited timetable without starting a run."""

    dataset_id: str = "small-college"
    schedule: dict[str, ScheduledSlot]
    weights: Weights = Weights()


class ValidateRequest(BaseModel):
    dataset: Dataset

