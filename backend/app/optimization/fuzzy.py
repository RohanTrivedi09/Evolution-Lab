"""A Mamdani fuzzy inference system for timetable comfort.

Soft Computing spans fuzzy, neural and evolutionary methods; the rest of this project
is evolutionary. This layer is the fuzzy one, and it is not decoration: crisp soft
penalties force a hard line where human judgement has none. Nobody believes two idle
periods is exactly twice as bad as one, or that a day is "fragmented" the instant a
gap appears. Membership functions let a schedule be partly comfortable.

Inference is textbook Mamdani: fuzzify the inputs, take min for AND and max for OR,
clip each consequent to its rule strength, aggregate with max, and defuzzify by
centroid.
"""
from __future__ import annotations

from dataclasses import dataclass

# Triangular sets as (left foot, peak, right foot). A shoulder is written with its
# foot at the peak so membership stays 1 beyond it.
LOW = (0.0, 0.0, 0.45)
MEDIUM = (0.20, 0.50, 0.80)
HIGH = (0.55, 1.0, 1.0)

SLIGHT = (0.0, 0.0, 0.40)
MODERATE = (0.20, 0.50, 0.80)
SEVERE = (0.60, 1.0, 1.0)

INPUT_SETS = {"low": LOW, "medium": MEDIUM, "high": HIGH}
OUTPUT_SETS = {"slight": SLIGHT, "moderate": MODERATE, "severe": SEVERE}
INPUT_NAMES = ("congestion", "fragmentation", "edge_load")

SAMPLES = 101


def triangular(x: float, shape: tuple[float, float, float]) -> float:
    """Membership of x in a triangular set, with flat shoulders at the ends."""
    left, peak, right = shape
    if x <= left and left == peak:
        return 1.0
    if x >= right and right == peak:
        return 1.0
    if x <= left or x >= right:
        return 0.0
    if x == peak:
        return 1.0
    if x < peak:
        return (x - left) / (peak - left)
    return (right - x) / (right - peak)


@dataclass(frozen=True)
class Rule:
    """One Mamdani rule. `mode` is how the antecedents combine."""

    text: str
    antecedents: tuple[tuple[str, str], ...]
    mode: str  # "and" -> min, "or" -> max
    consequent: str

    def strength(self, memberships: dict[str, dict[str, float]]) -> float:
        values = [memberships[variable][term] for variable, term in self.antecedents]
        return min(values) if self.mode == "and" else max(values)


RULES: tuple[Rule, ...] = (
    Rule("IF congestion is low AND fragmentation is low THEN discomfort is slight",
         (("congestion", "low"), ("fragmentation", "low")), "and", "slight"),
    Rule("IF congestion is medium OR fragmentation is medium THEN discomfort is moderate",
         (("congestion", "medium"), ("fragmentation", "medium")), "or", "moderate"),
    Rule("IF congestion is high OR fragmentation is high THEN discomfort is severe",
         (("congestion", "high"), ("fragmentation", "high")), "or", "severe"),
    Rule("IF edge_load is high THEN discomfort is moderate",
         (("edge_load", "high"),), "or", "moderate"),
    Rule("IF edge_load is low AND congestion is low THEN discomfort is slight",
         (("edge_load", "low"), ("congestion", "low")), "and", "slight"),
)


def fuzzify(inputs: dict[str, float]) -> dict[str, dict[str, float]]:
    return {
        name: {term: triangular(inputs[name], shape) for term, shape in INPUT_SETS.items()}
        for name in INPUT_NAMES
    }


def infer(congestion: float, fragmentation: float, edge_load: float) -> dict:
    """Return the defuzzified discomfort in [0, 1] plus the reasoning behind it."""
    clamp = lambda v: min(1.0, max(0.0, v))
    inputs = {"congestion": clamp(congestion), "fragmentation": clamp(fragmentation),
              "edge_load": clamp(edge_load)}
    memberships = fuzzify(inputs)

    firings = []
    clipped: dict[str, float] = {term: 0.0 for term in OUTPUT_SETS}
    for rule in RULES:
        strength = rule.strength(memberships)
        # Aggregate by max: several rules may drive the same consequent.
        clipped[rule.consequent] = max(clipped[rule.consequent], strength)
        if strength > 0:
            firings.append({"rule": rule.text, "consequent": rule.consequent,
                            "strength": round(strength, 4)})

    # Centroid defuzzification over the aggregated, clipped output sets.
    weighted = area = 0.0
    for index in range(SAMPLES):
        x = index / (SAMPLES - 1)
        height = max(min(level, triangular(x, OUTPUT_SETS[term]))
                     for term, level in clipped.items())
        weighted += x * height
        area += height
    discomfort = (weighted / area) if area else 0.0

    return {
        "discomfort": round(discomfort, 4),
        "inputs": {k: round(v, 4) for k, v in inputs.items()},
        "memberships": {k: {t: round(v, 4) for t, v in m.items()}
                        for k, m in memberships.items()},
        "firings": sorted(firings, key=lambda f: -f["strength"]),
    }


def profile() -> dict:
    """Sampled membership curves and the rule base, for plotting and explanation."""
    universe = [round(i / (SAMPLES - 1), 3) for i in range(SAMPLES)]
    curve = lambda sets: {term: [round(triangular(x, shape), 4) for x in universe]
                          for term, shape in sets.items()}
    return {
        "universe": universe,
        "inputs": {name: curve(INPUT_SETS) for name in INPUT_NAMES},
        "output": curve(OUTPUT_SETS),
        "rules": [rule.text for rule in RULES],
        "defuzzification": "centroid",
    }
