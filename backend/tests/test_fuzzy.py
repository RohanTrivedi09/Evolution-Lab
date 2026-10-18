"""Mamdani fuzzy comfort: membership, inference, and its effect on scoring."""
from __future__ import annotations

import pytest

from app.data import load_dataset
from app.models import Weights
from app.optimization import Problem, evaluate
from app.optimization.fuzzy import (HIGH, LOW, MEDIUM, RULES, fuzzify, infer,
                                    profile, triangular)

from factories import build, course, place


# --- membership functions -------------------------------------------------------------

def test_triangle_peaks_at_one_and_vanishes_outside_its_support():
    assert triangular(0.5, MEDIUM) == 1.0
    assert triangular(0.2, MEDIUM) == 0.0
    assert triangular(0.8, MEDIUM) == 0.0
    assert 0 < triangular(0.35, MEDIUM) < 1


def test_shoulders_stay_saturated_beyond_their_peak():
    """LOW peaks at 0 and HIGH at 1, so membership must not fall off the end."""
    assert triangular(0.0, LOW) == 1.0
    assert triangular(-0.5, LOW) == 1.0
    assert triangular(1.0, HIGH) == 1.0
    assert triangular(2.0, HIGH) == 1.0


def test_membership_is_continuous_across_the_ramp():
    values = [triangular(x / 100, MEDIUM) for x in range(20, 51)]
    assert values == sorted(values)


def test_fuzzify_covers_every_input_variable():
    memberships = fuzzify({"congestion": .5, "fragmentation": .5, "edge_load": .5})
    assert set(memberships) == {"congestion", "fragmentation", "edge_load"}
    assert set(memberships["congestion"]) == {"low", "medium", "high"}


# --- inference ------------------------------------------------------------------------

def test_discomfort_rises_with_a_worse_week():
    calm = infer(0.0, 0.0, 0.0)["discomfort"]
    middling = infer(0.5, 0.5, 0.5)["discomfort"]
    broken = infer(1.0, 1.0, 1.0)["discomfort"]
    assert calm < middling < broken


@pytest.mark.parametrize("args", [(0, 0, 0), (0.5, 0.5, 0.5), (1, 1, 1), (0.3, 0.9, 0.1)])
def test_discomfort_stays_inside_the_unit_interval(args):
    assert 0.0 <= infer(*args)["discomfort"] <= 1.0


def test_out_of_range_inputs_are_clamped_not_extrapolated():
    assert infer(5.0, -3.0, 0.5)["inputs"] == {"congestion": 1.0, "fragmentation": 0.0,
                                               "edge_load": 0.5}


def test_inference_reports_which_rules_fired():
    report = infer(0.95, 0.95, 0.1)
    assert report["firings"], "a fully congested week should fire something"
    assert any(f["consequent"] == "severe" for f in report["firings"])
    strengths = [f["strength"] for f in report["firings"]]
    assert strengths == sorted(strengths, reverse=True)
    assert all(0 < f["strength"] <= 1 for f in report["firings"])


def test_inference_is_deterministic():
    assert infer(0.4, 0.6, 0.2) == infer(0.4, 0.6, 0.2)


def test_profile_exposes_the_rule_base_for_explanation():
    p = profile()
    assert p["defuzzification"] == "centroid"
    assert len(p["rules"]) == len(RULES)
    assert set(p["inputs"]) == {"congestion", "fragmentation", "edge_load"}
    assert all(len(curve) == len(p["universe"])
               for sets in p["inputs"].values() for curve in sets.values())


# --- integration with scoring ---------------------------------------------------------

def test_fuzzy_is_off_by_default():
    problem = Problem(load_dataset("small-college"))
    score = evaluate(problem, problem.random_candidate(__import__("random").Random(1)), Weights())
    assert score.fuzzy is None


def test_enabling_fuzzy_reports_its_reasoning():
    problem = Problem(load_dataset("small-college"))
    candidate = problem.random_candidate(__import__("random").Random(1))
    score = evaluate(problem, candidate, Weights(fuzzy=True))
    assert score.fuzzy is not None
    assert 0.0 <= score.fuzzy["discomfort"] <= 1.0
    assert set(score.fuzzy["inputs"]) == {"congestion", "fragmentation", "edge_load"}


def test_fuzzy_changes_only_the_comfort_term_never_the_violations():
    """Hard constraints must stay dominant and untouched by the comfort model."""
    problem = build(courses=[course("C1", sessions=2)])
    candidate = place((0, 0, "R1"), (0, 2, "R1"))
    crisp = evaluate(problem, candidate, Weights())
    fuzzy = evaluate(problem, candidate, Weights(fuzzy=True))
    assert crisp.hard_violations == fuzzy.hard_violations
    assert crisp.soft_violations == fuzzy.soft_violations
    assert crisp.group_gaps == fuzzy.group_gaps
    assert crisp.daily_fragmentation == fuzzy.daily_fragmentation
    assert crisp.total_cost != fuzzy.total_cost


def test_fuzzy_scoring_stays_reproducible():
    problem = Problem(load_dataset("small-college"))
    candidate = problem.random_candidate(__import__("random").Random(2))
    first = evaluate(problem, candidate, Weights(fuzzy=True))
    second = evaluate(problem, candidate, Weights(fuzzy=True))
    assert first.total_cost == second.total_cost


def test_profile_endpoint_is_served():
    from fastapi.testclient import TestClient
    from app.main import app
    payload = TestClient(app).get("/api/fuzzy/profile").json()
    assert payload["rules"] and payload["output"]
