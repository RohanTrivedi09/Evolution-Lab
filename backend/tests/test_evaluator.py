"""One test per constraint. The evaluator is the contract every algorithm shares."""
from __future__ import annotations

from app.models import Weights
from app.optimization import Assignment, evaluate

from factories import BASE, LAB_COURSE, build, course, place


def counts(problem, candidate, weights=None):
    score = evaluate(problem, candidate, weights or Weights())
    return score, score.hard_breakdown, score.soft_breakdown


# --- hard constraints -----------------------------------------------------------------

def test_out_of_domain_placement_is_hard():
    problem = build()
    score, hard, _ = counts(problem, place((99, 0, "R1")))
    assert hard == {"domain": 1}
    assert score.hard_violations == 1


def test_room_type_must_match():
    problem = build(courses=[LAB_COURSE])
    score, hard, _ = counts(problem, place((0, 1, "R1")))
    assert hard.get("room_type") == 1


def test_an_oversubscribed_room_is_not_a_violation():
    """Capacity was dropped on purpose, so assert its absence rather than leave a gap.

    The timetables this project models state neither room sizes nor batch sizes, so
    enforcing capacity meant scoring numbers nobody supplied.
    """
    problem = build(groups=[{"id": "G1", "size": 80}, {"id": "G2", "size": 30}])
    _, hard, _ = counts(problem, place((0, 1, "R1")))  # R1 seats 50
    assert "capacity" not in hard
    assert not hard


def test_a_dataset_without_sizes_still_validates_and_scores():
    rooms = [{k: v for k, v in room.items() if k != "capacity"} for room in BASE["rooms"]]
    groups = [{"id": group["id"]} for group in BASE["groups"]]
    problem = build(rooms=rooms, groups=groups)
    score = evaluate(problem, place((0, 1, "R1")), Weights())
    assert score.hard_violations == 0


def test_faculty_unavailable_period_is_hard():
    problem = build(faculty=[{"id": "F1", "name": "Dr One",
                             "unavailable": [{"day": "Mon", "period": "10:00"}]},
                            {"id": "F2", "name": "Dr Two"}])
    score, hard, _ = counts(problem, place((0, 1, "R1")))
    assert hard.get("faculty_availability") == 1


def test_two_sessions_in_one_room_and_slot_clash():
    problem = build(courses=[
        course("C1", faculty="F1", groups=("G1",)),
        course("C2", faculty="F2", groups=("G2",)),
    ])
    score, hard, _ = counts(problem, place((0, 1, "R1"), (0, 1, "R1")))
    assert hard.get("room_conflict") == 1
    assert "faculty_conflict" not in hard and "group_conflict" not in hard


def test_one_teacher_cannot_be_in_two_places():
    problem = build(courses=[
        course("C1", faculty="F1", groups=("G1",)),
        course("C2", faculty="F1", groups=("G2",)),
    ])
    score, hard, _ = counts(problem, place((0, 1, "R1"), (0, 1, "R2")))
    assert hard.get("faculty_conflict") == 1
    assert "room_conflict" not in hard


def test_one_group_cannot_attend_two_sessions():
    problem = build(courses=[
        course("C1", faculty="F1", groups=("G1",)),
        course("C2", faculty="F2", groups=("G1",)),
    ])
    score, hard, _ = counts(problem, place((0, 1, "R1"), (0, 1, "R2")))
    assert hard.get("group_conflict") == 1
    assert "room_conflict" not in hard


def test_every_hard_violation_has_exactly_one_detail_row():
    """Regression: conflicts used to be counted per session but reported per slot."""
    problem = build(courses=[
        course(f"C{n}", sessions=2) for n in range(1, 4)
    ])
    candidate = [Assignment(0, 0, "R1") for _ in problem.sessions]
    score = evaluate(problem, candidate, Weights())
    hard_rows = [d for d in score.violation_details if d["severity"] == "hard"]
    assert len(hard_rows) == score.hard_violations
    assert sum(score.hard_breakdown.values()) == score.hard_violations


# --- soft constraints -----------------------------------------------------------------

def test_missing_a_preferred_period_is_soft():
    problem = build(courses=[
        course("C1", preferred_periods=[{"day": "Mon", "period": "10:00"}])])
    _, hard, soft = counts(problem, place((1, 1, "R1")))
    assert soft.get("preferred_period_miss") == 1
    assert not hard
    _, _, soft_hit = counts(problem, place((0, 1, "R1")))
    assert "preferred_period_miss" not in soft_hit


def test_faculty_undesirable_period_is_soft_not_hard():
    problem = build(faculty=[{"id": "F1", "name": "Dr One",
                             "undesirable": [{"day": "Mon", "period": "10:00"}]},
                            {"id": "F2", "name": "Dr Two"}])
    _, hard, soft = counts(problem, place((0, 1, "R1")))
    assert soft.get("faculty_undesirable") == 1
    assert not hard


def test_first_and_last_periods_are_penalised():
    problem = build()
    assert counts(problem, place((0, 0, "R1")))[2].get("edge_period") == 1
    assert counts(problem, place((0, 2, "R1")))[2].get("edge_period") == 1
    assert "edge_period" not in counts(problem, place((0, 1, "R1")))[2]


def test_repeated_sessions_should_spread_across_days():
    problem = build(courses=[course("C1", sessions=2)])
    same_day = counts(problem, place((0, 0, "R1"), (0, 1, "R1")))[2]
    assert same_day.get("same_day_repeat") == 1
    spread = counts(problem, place((0, 0, "R1"), (1, 1, "R1")))[2]
    assert "same_day_repeat" not in spread


def test_group_gaps_and_fragmentation_track_a_broken_day():
    problem = build(courses=[course("C1", sessions=2)])
    score = evaluate(problem, place((0, 0, "R1"), (0, 2, "R1")), Weights())
    assert score.group_gaps == 1
    assert score.daily_fragmentation == 1

    contiguous = evaluate(problem, place((0, 0, "R1"), (0, 1, "R1")), Weights())
    assert contiguous.group_gaps == 0
    assert contiguous.daily_fragmentation == 0


def test_room_changes_within_a_day_are_penalised():
    problem = build(courses=[course("C1", sessions=2)])
    moved = counts(problem, place((0, 0, "R1"), (0, 1, "R2")))[2]
    assert moved.get("room_change") == 1
    stayed = counts(problem, place((0, 0, "R1"), (0, 1, "R1")))[2]
    assert "room_change" not in stayed


# --- scoring --------------------------------------------------------------------------

def test_weights_combine_the_objectives(unit_weights):
    problem = build(courses=[course("C1", sessions=2)])
    score = evaluate(problem, place((0, 0, "R1"), (0, 2, "R1")), unit_weights)
    expected = (score.hard_violations + score.soft_violations
                + score.group_gaps + score.daily_fragmentation)
    assert score.total_cost == expected


def test_normalized_fitness_falls_as_cost_rises():
    problem = build()
    good = evaluate(problem, place((0, 1, "R1")), Weights())
    bad = evaluate(problem, place((99, 0, "R1")), Weights())
    assert bad.total_cost > good.total_cost
    assert bad.normalized_fitness < good.normalized_fitness
    assert 0 < good.normalized_fitness <= 1


def test_evaluation_is_pure(weights):
    """Scoring must not mutate the candidate; algorithms rely on that."""
    problem = build()
    candidate = place((0, 1, "R1"))
    before = [a.key() for a in candidate]
    evaluate(problem, candidate, weights)
    assert [a.key() for a in candidate] == before
