"""Multi-objective search: dominance, non-dominated sorting, and the returned front."""
from __future__ import annotations

import math

import pytest

from app.data import load_dataset
from app.models import Weights
from app.optimization import Problem, optimizer_for
from app.optimization import base as base_module
from app.optimization.pareto import (OBJECTIVE_KEYS, crowding_distance, dominates,
                                     non_dominated_sort, vector)


# --- dominance ------------------------------------------------------------------------

@pytest.mark.parametrize("left,right,expected", [
    ((1, 1), (2, 2), True),    # better on both
    ((1, 2), (2, 2), True),    # better on one, equal on the other
    ((2, 2), (1, 1), False),   # worse on both
    ((1, 3), (3, 1), False),   # a genuine trade-off: neither dominates
    ((2, 2), (2, 2), False),   # identical vectors never dominate each other
])
def test_dominance_truth_table(left, right, expected):
    assert dominates(left, right) is expected


def test_dominance_is_antisymmetric():
    a, b = (1.0, 5.0), (2.0, 4.0)
    assert not (dominates(a, b) and dominates(b, a))


def test_vector_uses_the_specified_objective_order():
    objectives = {"hard_violations": 1, "soft_penalty": 2,
                  "group_gaps": 3, "room_utilisation_imbalance": 4}
    assert vector(objectives) == (1.0, 2.0, 3.0, 4.0)
    assert vector({}) == (0.0, 0.0, 0.0, 0.0)


# --- sorting --------------------------------------------------------------------------

def test_a_known_set_sorts_into_the_expected_fronts():
    #   (1,4) (2,2) (4,1) are mutually non-dominated -> front 0
    #   (3,3) is beaten by (2,2)                     -> front 1
    #   (5,5) is beaten by everything                -> front 2
    vectors = [(1, 4), (2, 2), (4, 1), (3, 3), (5, 5)]
    fronts = non_dominated_sort(vectors)
    assert [sorted(f) for f in fronts] == [[0, 1, 2], [3], [4]]


def test_every_member_of_the_first_front_is_non_dominated():
    vectors = [(1, 4), (2, 2), (4, 1), (3, 3), (5, 5)]
    first = non_dominated_sort(vectors)[0]
    assert not any(dominates(vectors[b], vectors[a]) for a in first for b in range(len(vectors)))


def test_all_solutions_are_assigned_to_exactly_one_front():
    vectors = [(1, 4), (2, 2), (4, 1), (3, 3), (5, 5)]
    placed = [i for front in non_dominated_sort(vectors) for i in front]
    assert sorted(placed) == list(range(len(vectors)))


def test_identical_solutions_share_the_first_front():
    fronts = non_dominated_sort([(1, 1), (1, 1), (2, 2)])
    assert sorted(fronts[0]) == [0, 1]


# --- crowding -------------------------------------------------------------------------

def test_boundary_solutions_are_kept_by_infinite_distance():
    """Without this the front collapses toward its middle as selection proceeds."""
    vectors = [(1, 5), (3, 3), (5, 1)]
    distance = crowding_distance(vectors, [0, 1, 2])
    assert distance[0] == math.inf and distance[2] == math.inf
    assert 0 < distance[1] < math.inf


def test_a_tiny_front_is_entirely_boundary():
    assert all(d == math.inf for d in crowding_distance([(1, 1), (2, 2)], [0, 1]).values())


def test_an_objective_everyone_ties_on_contributes_nothing():
    vectors = [(1, 7), (2, 7), (3, 7)]
    distance = crowding_distance(vectors, [0, 1, 2])
    assert distance[1] < math.inf  # the tied axis must not divide by a zero span


# --- the algorithm --------------------------------------------------------------------

@pytest.fixture
def problem() -> Problem:
    return Problem(load_dataset("small-college"))


def test_nsga2_returns_a_genuinely_non_dominated_front(problem):
    result = optimizer_for("nsga2", problem, Weights(), 42, {}, max_evaluations=1500).run()
    front = result.pareto_front
    assert front, "expected a non-empty front"
    vectors = [vector(row["objectives"]) for row in front]
    assert not any(dominates(vectors[i], vectors[j])
                   for i in range(len(vectors)) for j in range(len(vectors)) if i != j)


def test_a_tiny_instance_has_no_trade_offs_to_offer(problem):
    """Recorded because it is a finding, not a failure.

    On the nine-session demo set the front collapses to a single point at every seed
    and budget tried: once a schedule is feasible the remaining objectives stop
    competing, so there is nothing to choose between. Multi-objective search only earns
    its keep on an instance where the objectives genuinely conflict.
    """
    result = optimizer_for("nsga2", problem, Weights(), 7, {}, max_evaluations=2500).run()
    assert result.pareto_front
    assert all(row["hard_violations"] == 0 for row in result.pareto_front)
    assert len({vector(row["objectives"]) for row in result.pareto_front}) == 1


def test_every_front_entry_carries_a_complete_timetable(problem):
    result = optimizer_for("nsga2", problem, Weights(), 3, {}, max_evaluations=900).run()
    for row in result.pareto_front:
        assert set(row["objectives"]) == set(OBJECTIVE_KEYS)
        assert len(row["schedule"]) == len(problem.sessions)


def test_nsga2_respects_its_budget_and_reports_it_honestly(problem, monkeypatch):
    calls = {"n": 0}
    original = base_module.evaluate

    def counting(prob, candidate, weights):
        calls["n"] += 1
        return original(prob, candidate, weights)

    monkeypatch.setattr(base_module, "evaluate", counting)
    result = optimizer_for("nsga2", problem, Weights(), 42, {}, max_evaluations=800).run()
    assert result.evaluations == calls["n"] <= 800


def test_nsga2_still_reports_a_scalar_best(problem):
    """The dashboard, replay and experiments all read the scalar contract."""
    result = optimizer_for("nsga2", problem, Weights(), 42, {}, max_evaluations=900).run()
    assert len(result.candidate) == len(problem.sessions)
    assert result.score.total_cost >= 0
    assert result.history and result.history[-1]["evaluations"] <= 900


def test_single_objective_strategies_return_no_front(problem):
    result = optimizer_for("hill_climbing", problem, Weights(), 1, {}, max_evaluations=200).run()
    assert result.pareto_front == []


def test_nsga2_is_reproducible(problem):
    runs = [optimizer_for("nsga2", problem, Weights(), 11, {}, max_evaluations=700).run()
            for _ in range(2)]
    assert ([vector(r["objectives"]) for r in runs[0].pareto_front]
            == [vector(r["objectives"]) for r in runs[1].pareto_front])


def test_a_scalar_race_excludes_nsga2():
    """Ranking a vector optimiser against scalar ones compares different questions."""
    from app.optimization import COMPARISON_STRATEGIES, STRATEGIES
    assert "nsga2" in STRATEGIES
    assert "nsga2" not in COMPARISON_STRATEGIES


def test_the_front_never_offers_an_infeasible_timetable_as_a_trade_off(problem):
    """Hard constraints dominate. A schedule with clashes is invalid, not a compromise.

    Pareto dominance alone would keep one: two clashes with perfect room balance is
    formally non-dominated. Reporting it as a choice would contradict the evaluator.
    """
    result = optimizer_for("nsga2", problem, Weights(), 42, {}, max_evaluations=3000).run()
    assert result.pareto_front
    assert all(row["hard_violations"] == 0 for row in result.pareto_front)


def test_an_infeasible_search_still_returns_its_best_efforts(problem):
    """With almost no budget nothing is feasible; an empty front would be less useful."""
    result = optimizer_for("nsga2", problem, Weights(), 5, {}, max_evaluations=8).run()
    assert result.pareto_front, "expected the raw front when nothing feasible was found"


@pytest.mark.parametrize("left,right,lv,rv,expected", [
    ((9, 9), (0, 0), 0, 3, True),    # feasible beats infeasible regardless of objectives
    ((0, 0), (9, 9), 3, 0, False),   # and infeasible never beats feasible
    ((9, 9), (0, 0), 1, 5, True),    # among infeasible, fewer violations wins
    ((1, 1), (2, 2), 0, 0, True),    # both feasible: ordinary dominance
    ((1, 1), (2, 2), 4, 4, True),    # equal violations: fall through to the objectives
    ((2, 2), (1, 1), 4, 4, False),
    ((1, 2), (2, 1), 4, 4, False),   # equal violations, genuine trade-off: neither wins
])
def test_constrained_domination_truth_table(left, right, lv, rv, expected):
    from app.optimization.pareto import constrained_dominates
    assert constrained_dominates(left, right, lv, rv) is expected


def test_constrained_sorting_puts_every_feasible_solution_ahead():
    from app.optimization.pareto import non_dominated_sort
    # Two feasible solutions that trade off against each other, and one infeasible
    # solution whose objectives look better than both.
    vectors = [(9, 1), (1, 1), (1, 9)]
    fronts = non_dominated_sort(vectors, violations=[0, 2, 0])
    assert sorted(fronts[0]) == [0, 2], "both feasible trade-offs belong in the first front"
    assert fronts[1] == [1], "the infeasible solution ranks behind them despite better objectives"


def test_a_denser_instance_does_offer_competing_trade_offs():
    """The counterpart to the degenerate case: objectives must actually compete.

    Thirteen sessions is enough for compactness, preferences and room balance to pull
    against one another, so the front holds several feasible schedules that are each
    better at something.
    """
    problem = Problem(load_dataset("medium-college"))
    result = optimizer_for("nsga2", problem, Weights(), 42, {}, max_evaluations=2000).run()
    front = result.pareto_front
    assert all(row["hard_violations"] == 0 for row in front)
    assert len({vector(row["objectives"]) for row in front}) > 1, \
        "expected competing trade-offs on a denser instance"
