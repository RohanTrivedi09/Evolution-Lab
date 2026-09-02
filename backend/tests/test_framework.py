import pytest
from app.data import load_dataset
from app.models import Weights
from app.optimization import Problem, optimizer_for

@pytest.fixture
def problem():
    return Problem(load_dataset("small-college"))

def test_expansion_and_evaluator_are_shared(problem):
    assert len(problem.sessions) == 9
    candidate = problem.random_candidate(__import__("random").Random(4))
    score = problem.evaluate(candidate, Weights())
    assert score.total_cost >= 0
    assert isinstance(score.violation_details, list)

@pytest.mark.parametrize("name", ["hill_climbing", "simulated_annealing", "genetic_algorithm", "particle_swarm"])
def test_strategies_return_same_contract(problem, name):
    result = optimizer_for(name, problem, Weights(), 42, {"iterations": 3, "generations": 3, "population_size": 5, "swarm_size": 5}).run()
    assert len(result.candidate) == len(problem.sessions)
    assert len(result.history) == 3
    assert result.history[0]["schedule"]
    assert result.score.total_cost >= 0
    assert result.evaluations > 0

def test_seeded_strategy_is_reproducible(problem):
    first = optimizer_for("hill_climbing", problem, Weights(), 7, {"iterations": 5}).run()
    second = optimizer_for("hill_climbing", problem, Weights(), 7, {"iterations": 5}).run()
    assert first.score.as_dict() == second.score.as_dict()
    assert [(a.day, a.period, a.room) for a in first.candidate] == [(a.day, a.period, a.room) for a in second.candidate]
