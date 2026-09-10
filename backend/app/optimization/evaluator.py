"""The shared fitness evaluator.

Every algorithm scores candidates through this module, so comparisons are fair by
construction. Hard constraints dominate; soft constraints express preferences.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Weights
from .fuzzy import infer
from .representation import Candidate, Problem

HARD_CATEGORIES = ("domain", "room_type", "capacity", "faculty_availability",
                   "room_conflict", "faculty_conflict", "group_conflict")
SOFT_CATEGORIES = ("preferred_period_miss", "faculty_undesirable", "edge_period",
                   "same_day_repeat", "room_change", "group_gap", "fragmentation")


@dataclass
class Score:
    total_cost: float
    normalized_fitness: float
    hard_violations: int
    soft_violations: int
    group_gaps: int
    daily_fragmentation: int
    violation_details: list[dict]
    fuzzy: dict | None = None
    objectives: dict[str, float] = field(default_factory=dict)
    soft_breakdown: dict[str, int] = field(default_factory=dict)
    hard_breakdown: dict[str, int] = field(default_factory=dict)
    cost_by_course: dict[str, float] = field(default_factory=dict)
    cost_by_group: dict[str, float] = field(default_factory=dict)
    cost_by_faculty: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


class _Ledger:
    """Collects violations and attributes their cost to courses, groups and faculty."""

    def __init__(self) -> None:
        self.details: list[dict] = []
        self.by_course: dict[str, float] = {}
        self.by_group: dict[str, float] = {}
        self.by_faculty: dict[str, float] = {}

    def add(self, *, session_id: str, category: str, severity: str, message: str,
            cost: float, course_id: str | None = None, faculty_id: str | None = None,
            group_ids: tuple[str, ...] = ()) -> None:
        self.details.append({
            "session_id": session_id, "category": category, "severity": severity,
            "message": message, "cost": cost,
        })
        if course_id:
            self.by_course[course_id] = self.by_course.get(course_id, 0.0) + cost
        if faculty_id:
            self.by_faculty[faculty_id] = self.by_faculty.get(faculty_id, 0.0) + cost
        for group in group_ids:
            self.by_group[group] = self.by_group.get(group, 0.0) + cost


def _contiguous_blocks(periods: list[int]) -> int:
    """Number of unbroken runs in a sorted list of distinct period indexes."""
    ordered = sorted(set(periods))
    if not ordered:
        return 0
    return 1 + sum(1 for a, b in zip(ordered, ordered[1:]) if b - a > 1)


def evaluate(problem: Problem, candidate: Candidate, weights: Weights) -> Score:
    dataset = problem.dataset
    ledger = _Ledger()
    hard_counts = {name: 0 for name in HARD_CATEGORIES}
    soft_counts = {name: 0 for name in SOFT_CATEGORIES}

    placed: list[tuple[int, object, object]] = []
    for index, (session, assignment) in enumerate(zip(problem.sessions, candidate)):
        if not problem.in_domain(assignment):
            hard_counts["domain"] += 1
            ledger.add(session_id=session.id, category="domain", severity="hard",
                       message="Assignment is outside the valid domain", cost=weights.hard,
                       course_id=session.course_id, faculty_id=session.faculty_id,
                       group_ids=session.group_ids)
            continue
        placed.append((index, session, assignment))

    # --- Per-session hard constraints -------------------------------------------------
    for _, session, assignment in placed:
        room = problem.rooms[assignment.room]
        day_name = dataset.days[assignment.day]
        period_name = dataset.periods[assignment.period]

        if room.type != session.room_type:
            hard_counts["room_type"] += 1
            ledger.add(session_id=session.id, category="room_type", severity="hard",
                       message=f"Room {room.id} is a {room.type}, but this session needs a {session.room_type}",
                       cost=weights.hard, course_id=session.course_id,
                       faculty_id=session.faculty_id, group_ids=session.group_ids)

        largest = max((problem.groups[g].size for g in session.group_ids), default=0)
        if room.capacity < largest:
            hard_counts["capacity"] += 1
            ledger.add(session_id=session.id, category="capacity", severity="hard",
                       message=f"Room capacity {room.capacity} is below group size {largest}",
                       cost=weights.hard, course_id=session.course_id,
                       faculty_id=session.faculty_id, group_ids=session.group_ids)

        member = problem.faculty[session.faculty_id]
        if any(slot.day == day_name and slot.period == period_name for slot in member.unavailable):
            hard_counts["faculty_availability"] += 1
            ledger.add(session_id=session.id, category="faculty_availability", severity="hard",
                       message=f"{member.name} is unavailable at {day_name} {period_name}",
                       cost=weights.hard, course_id=session.course_id,
                       faculty_id=session.faculty_id, group_ids=session.group_ids)

    # --- Resource clashes -------------------------------------------------------------
    # One violation, and one detail row, per session that has to give way.
    def clashes(bucket: dict[tuple, list], category: str, describe) -> None:
        for key, members in bucket.items():
            for session in members[1:]:
                hard_counts[category] += 1
                ledger.add(session_id=session.id, category=category, severity="hard",
                           message=describe(key), cost=weights.hard,
                           course_id=session.course_id, faculty_id=session.faculty_id,
                           group_ids=session.group_ids)

    rooms: dict[tuple, list] = {}
    teachers: dict[tuple, list] = {}
    cohorts: dict[tuple, list] = {}
    for _, session, assignment in placed:
        slot = (assignment.day, assignment.period)
        rooms.setdefault((assignment.room, *slot), []).append(session)
        teachers.setdefault((session.faculty_id, *slot), []).append(session)
        for group in session.group_ids:
            cohorts.setdefault((group, *slot), []).append(session)

    at = lambda key: f"{dataset.days[key[1]]} {dataset.periods[key[2]]}"
    clashes(rooms, "room_conflict", lambda k: f"Room {k[0]} is double-booked at {at(k)}")
    clashes(teachers, "faculty_conflict", lambda k: f"{k[0]} has overlapping sessions at {at(k)}")
    clashes(cohorts, "group_conflict", lambda k: f"{k[0]} has overlapping sessions at {at(k)}")

    # --- Per-session soft preferences -------------------------------------------------
    last_period = problem.period_count - 1
    for _, session, assignment in placed:
        slot = (assignment.day, assignment.period)
        day_name = dataset.days[assignment.day]
        period_name = dataset.periods[assignment.period]

        preferences = problem.course_preferences.get(session.course_id)
        if preferences and slot not in preferences:
            soft_counts["preferred_period_miss"] += 1
            ledger.add(session_id=session.id, category="preferred_period_miss", severity="soft",
                       message=f"{session.name} prefers another slot than {day_name} {period_name}",
                       cost=weights.soft, course_id=session.course_id,
                       faculty_id=session.faculty_id, group_ids=session.group_ids)

        if slot in problem.faculty_undesirable.get(session.faculty_id, ()):
            soft_counts["faculty_undesirable"] += 1
            ledger.add(session_id=session.id, category="faculty_undesirable", severity="soft",
                       message=f"{day_name} {period_name} is an undesirable period for {session.faculty_id}",
                       cost=weights.soft, course_id=session.course_id,
                       faculty_id=session.faculty_id, group_ids=session.group_ids)

        if problem.period_count > 2 and assignment.period in (0, last_period):
            soft_counts["edge_period"] += 1
            ledger.add(session_id=session.id, category="edge_period", severity="soft",
                       message=f"Sits in an edge period ({period_name})", cost=weights.soft,
                       course_id=session.course_id, faculty_id=session.faculty_id,
                       group_ids=session.group_ids)

    # Repeated sessions of one course should spread across the week.
    for course_id, indexes in problem.sessions_by_course.items():
        seen: dict[int, int] = {}
        for index in indexes:
            assignment = candidate[index]
            if not problem.in_domain(assignment):
                continue
            seen[assignment.day] = seen.get(assignment.day, 0) + 1
            if seen[assignment.day] > 1:
                session = problem.sessions[index]
                soft_counts["same_day_repeat"] += 1
                ledger.add(session_id=session.id, category="same_day_repeat", severity="soft",
                           message=f"Another {course_id} session already sits on {dataset.days[assignment.day]}",
                           cost=weights.soft, course_id=course_id,
                           faculty_id=session.faculty_id, group_ids=session.group_ids)

    # --- Per-group daily shape --------------------------------------------------------
    gaps = 0
    fragmentation = 0
    active_group_days = 0
    for group_id in problem.groups:
        by_day: dict[int, list[tuple[int, str]]] = {}
        for _, session, assignment in placed:
            if group_id in session.group_ids:
                by_day.setdefault(assignment.day, []).append((assignment.period, assignment.room))
        active_group_days += len(by_day)
        for day, entries in by_day.items():
            periods = [period for period, _ in entries]
            holes = len(set(range(min(periods), max(periods) + 1)) - set(periods))
            blocks = _contiguous_blocks(periods) - 1
            gaps += holes
            fragmentation += blocks
            if holes:
                soft_counts["group_gap"] += holes
                ledger.add(session_id=f"{group_id}@{dataset.days[day]}", category="group_gap",
                           severity="soft", message=f"{group_id} has {holes} idle period(s) on {dataset.days[day]}",
                           cost=weights.gaps * holes, group_ids=(group_id,))
            if blocks:
                soft_counts["fragmentation"] += blocks
                ledger.add(session_id=f"{group_id}@{dataset.days[day]}", category="fragmentation",
                           severity="soft", message=f"{group_id}'s {dataset.days[day]} is split into {blocks + 1} blocks",
                           cost=weights.fragmentation * blocks, group_ids=(group_id,))

            moves = sum(1 for (_, a), (_, b) in zip(sorted(entries), sorted(entries)[1:]) if a != b)
            if moves:
                soft_counts["room_change"] += moves
                ledger.add(session_id=f"{group_id}@{dataset.days[day]}", category="room_change",
                           severity="soft", message=f"{group_id} changes room {moves} time(s) on {dataset.days[day]}",
                           cost=weights.soft * moves, group_ids=(group_id,))

    # --- Aggregate --------------------------------------------------------------------
    hard = sum(hard_counts.values())
    soft = (soft_counts["preferred_period_miss"] + soft_counts["faculty_undesirable"]
            + soft_counts["edge_period"] + soft_counts["same_day_repeat"]
            + soft_counts["room_change"])

    usage: dict[str, int] = {room_id: 0 for room_id in problem.room_ids}
    for _, _, assignment in placed:
        usage[assignment.room] = usage.get(assignment.room, 0) + 1
    mean = sum(usage.values()) / max(1, len(usage))
    imbalance = sum(abs(count - mean) for count in usage.values()) / max(1, len(usage))

    # Crisp comfort: gaps and fragmentation priced linearly.
    comfort_cost = weights.gaps * gaps + weights.fragmentation * fragmentation
    fuzzy_report = None
    if weights.fuzzy:
        # Fuzzy comfort: nobody believes two idle periods is exactly twice as bad as
        # one, so the shape of the penalty is inferred rather than assumed linear.
        span = max(1, problem.period_count - 1)
        halves = max(1, problem.period_count // 2)
        fuzzy_report = infer(
            congestion=gaps / max(1, active_group_days * span),
            fragmentation=fragmentation / max(1, active_group_days * halves),
            edge_load=soft_counts["edge_period"] / max(1, len(placed)),
        )
        scale = (weights.gaps + weights.fragmentation) * max(1, len(problem.sessions))
        comfort_cost = fuzzy_report["discomfort"] * scale

    total = weights.hard * hard + weights.soft * soft + comfort_cost

    return Score(
        total_cost=total,
        normalized_fitness=1 / (1 + max(0.0, total)),
        hard_violations=hard,
        soft_violations=soft,
        group_gaps=gaps,
        daily_fragmentation=fragmentation,
        violation_details=ledger.details,
        fuzzy=fuzzy_report,
        objectives={
            "hard_violations": float(hard),
            "soft_penalty": float(soft),
            "group_gaps": float(gaps),
            "room_utilisation_imbalance": round(imbalance, 3),
        },
        soft_breakdown={k: v for k, v in soft_counts.items() if v},
        hard_breakdown={k: v for k, v in hard_counts.items() if v},
        cost_by_course=ledger.by_course,
        cost_by_group=ledger.by_group,
        cost_by_faculty=ledger.by_faculty,
    )
