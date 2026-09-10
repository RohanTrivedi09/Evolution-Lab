"""Algorithm invariants: shared contract, honest budgets, real operators."""
from __future__ import annotations

import random

import pytest

from app.data import load_dataset
from app.models import Weights
from app.optimization import (DEFAULT_BUDGET, OPERATORS, Problem, STRATEGIES,
                              optimizer_for, random_neighbor, resolve_budget)
from app.optimization import base as base_module
from app.optimization.genetic import GeneticAlgorithm

from factories import build, course

NAMES = list(STRATEGIES)


@pytest.fixture
def problem() -> Problem:
    return Problem(load_dataset("small-college"))


# --- shared contract ------------------------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_every_strategy_returns_the_same_shape(problem, name):
    result = optimizer_for(name, problem, Weights(), 42, {}, max_evaluations=300).run()
    assert len(result.candidate) == len(problem.sessions)
    assert result.score.total_cost >= 0
    assert result.history and result.trajectory
    latest = result.history[-1]
    assert {"iteration", "evaluations", "best_cost", "best_fitness",
            "hard_violations", "event"} <= set(latest)


@pytest.mark.parametrize("name", NAMES)
def test_history_best_cost_never_gets_worse(problem, name):
    result = optimizer_for(name, problem, Weights(), 7, {}, max_evaluations=400).run()
    costs = [point["best_cost"] for point in result.history]
    assert costs == sorted(costs, reverse=True)


# --- budget honesty -------------------------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_strategies_stay_inside_their_budget(problem, name):
    result = optimizer_for(name, problem, Weights(), 42, {}, max_evaluations=250).run()
    assert result.evaluations <= 250
    assert result.history[-1]["evaluations"] <= 250


@pytest.mark.parametrize("name", NAMES)
def test_reported_evaluations_match_actual_fitness_calls(problem, name, monkeypatch):
    """Regression: the GA used to evaluate during tournament selection off the books,
    reporting 3,000 evaluations while performing 11,700."""
    calls = {"n": 0}
    original = base_module.evaluate

    def counting(prob, candidate, weights):
        calls["n"] += 1
        return original(prob, candidate, weights)

    monkeypatch.setattr(base_module, "evaluate", counting)
    result = optimizer_for(name, problem, Weights(), 42, {}, max_evaluations=500).run()
    assert result.evaluations == calls["n"]


@pytest.mark.parametrize("name", NAMES)
def test_same_seed_gives_the_same_result(problem, name):
    runs = [optimizer_for(name, problem, Weights(), 11, {}, max_evaluations=300).run()
            for _ in range(2)]
    assert runs[0].score.total_cost == runs[1].score.total_cost
    assert ([a.key() for a in runs[0].candidate] == [a.key() for a in runs[1].candidate])


def test_budget_resolution_prefers_explicit_then_legacy_then_default():
    assert resolve_budget("hill_climbing", {"iterations": 80}, 999) == 999
    assert resolve_budget("hill_climbing", {"max_evaluations": 500}) == 500
    assert resolve_budget("hill_climbing", {"iterations": 80}) == 81
    assert resolve_budget("genetic_algorithm", {"generations": 10, "population_size": 4}) == 40
    assert resolve_budget("particle_swarm", {"iterations": 10, "swarm_size": 5}) == 50
    assert resolve_budget("hill_climbing", {}) == DEFAULT_BUDGET


# --- operators ------------------------------------------------------------------------

@pytest.mark.parametrize("operator", OPERATORS)
def test_operators_preserve_length_and_domain(problem, operator):
    rng = random.Random(3)
    candidate = problem.random_candidate(rng)
    for _ in range(50):
        child = operator(problem, candidate, rng)
        assert len(child) == len(candidate)
        assert all(problem.in_domain(a) for a in child)


def test_operators_do_not_mutate_their_input(problem):
    rng = random.Random(5)
    candidate = problem.random_candidate(rng)
    before = [a.key() for a in candidate]
    for _ in range(20):
        random_neighbor(problem, candidate, rng)
    assert [a.key() for a in candidate] == before


def test_a_neighbour_differs_from_its_parent(problem):
    rng = random.Random(9)
    candidate = problem.random_candidate(rng)
    changed = sum(1 for _ in range(40)
                  if random_neighbor(problem, candidate, rng)[0] != candidate)
    assert changed > 0


# --- genetic operators ----------------------------------------------------------------

@pytest.fixture
def ga(problem) -> GeneticAlgorithm:
    return GeneticAlgorithm(problem, Weights(), 1, {}, None, 500, None)


@pytest.mark.parametrize("style", ["_uniform_crossover", "_one_point_crossover"])
def test_crossover_children_only_carry_parent_genes(problem, ga, style):
    """Regression: the GA cloned a tournament winner and never recombined."""
    rng = random.Random(0)
    left, right = problem.random_candidate(rng), problem.random_candidate(rng)
    child = getattr(ga, style)(left, right)
    assert len(child) == len(left)
    assert all(gene.key() in (left[i].key(), right[i].key())
               for i, gene in enumerate(child))


def test_uniform_crossover_actually_mixes_both_parents(problem, ga):
    rng = random.Random(2)
    left, right = problem.random_candidate(rng), problem.random_candidate(rng)
    children = [ga._uniform_crossover(left, right) for _ in range(20)]
    from_right = {sum(1 for i, g in enumerate(c) if g.key() == right[i].key())
                  for c in children}
    assert len(from_right) > 1, "every child took the same parent - no recombination"


def test_tournament_selection_costs_no_evaluations(problem, ga):
    rng = random.Random(4)
    population = [(problem.random_candidate(rng), ga.score(problem.random_candidate(rng)))
                  for _ in range(6)]
    before = ga.evaluations
    for _ in range(50):
        ga._tournament(population, 3)
    assert ga.evaluations == before


# --- swarm ----------------------------------------------------------------------------

def test_particles_accumulate_their_mutations(problem):
    """Regression: `p = self.mutate(p)` rebound a local name, so a particle's own
    exploration never made it back into the swarm and positions could not drift.

    With attraction switched off and inertia at 1 each particle is a random walk, so
    the cloud of visited candidates must spread well beyond a single mutation.
    """
    result = optimizer_for("particle_swarm", problem, Weights(), 5,
                           {"swarm_size": 2, "w": 1.0, "c1": 0.0, "c2": 0.0},
                           max_evaluations=300).run()
    seen = [tuple(map(tuple, point["placement"])) for point in result.trajectory]
    spread = max(sum(1 for a, b in zip(left, right) if a != b)
                 for left in seen for right in seen)
    assert spread >= 4, f"particles never drifted (max distance {spread})"


# --- repair from an edited timetable --------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_a_run_can_start_from_a_supplied_schedule(problem, name):
    rng = random.Random(1)
    start = problem.to_schedule(problem.random_candidate(rng))
    result = optimizer_for(name, problem, Weights(), 42, {}, max_evaluations=1,
                           initial_schedule=start).run()
    assert problem.to_schedule(result.candidate) == start


def test_repairing_an_edit_does_not_make_it_worse(problem):
    rng = random.Random(8)
    start = problem.to_schedule(problem.random_candidate(rng))
    baseline = optimizer_for("hill_climbing", problem, Weights(), 3, {},
                             max_evaluations=1, initial_schedule=start).run()
    repaired = optimizer_for("hill_climbing", problem, Weights(), 3, {},
                             max_evaluations=400, initial_schedule=start).run()
    assert repaired.score.total_cost <= baseline.score.total_cost


# --- domain sanity --------------------------------------------------------------------

def test_sessions_expand_from_weekly_counts():
    problem = build(courses=[course("C1", sessions=3), course("C2", sessions=1)])
    assert [s.id for s in problem.sessions] == ["C1-1", "C1-2", "C1-3", "C2-1"]
    assert problem.sessions_by_course["C1"] == [0, 1, 2]
