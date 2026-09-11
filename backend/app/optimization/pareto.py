"""Pareto dominance primitives for multi-objective search.

Kept apart from any one algorithm so the definitions can be tested on their own: a
weighted sum collapses competing goals into a single number and hides the trade-off,
whereas dominance keeps them separate and admits that some schedules are simply
incomparable.
"""
from __future__ import annotations

import math

#: The objectives named in the project specification, in a fixed order so a vector
#: position always means the same thing. All are minimised.
OBJECTIVE_KEYS = ("hard_violations", "soft_penalty", "group_gaps",
                  "room_utilisation_imbalance")

Vector = tuple[float, ...]


def vector(objectives: dict[str, float]) -> Vector:
    return tuple(float(objectives.get(key, 0.0)) for key in OBJECTIVE_KEYS)


def dominates(left: Vector, right: Vector) -> bool:
    """True when `left` is at least as good everywhere and strictly better somewhere.

    Equal vectors do not dominate each other, which is what keeps distinct but equally
    good trade-offs alive in the same front.
    """
    no_worse = all(a <= b for a, b in zip(left, right))
    return no_worse and any(a < b for a, b in zip(left, right))


def constrained_dominates(left: Vector, right: Vector,
                          left_violations: int, right_violations: int) -> bool:
    """Deb's constrained-domination: feasibility outranks every objective.

    Plain dominance treats hard violations as one objective among four, so a schedule
    with two clashes and perfect room balance is formally non-dominated. This project
    treats hard constraints as dominant, and with a quarter of the selection pressure
    the search never drove them to zero. Here a feasible solution beats any infeasible
    one, and between two infeasible ones the smaller violation count wins.
    """
    if left_violations == 0 and right_violations > 0:
        return True
    if left_violations > 0 and right_violations == 0:
        return False
    if left_violations != right_violations:
        return left_violations < right_violations
    # Equal violation counts, so constraints separate nothing: fall through to the
    # objectives. Returning False here instead would leave plainly dominated solutions
    # sitting in the front.
    return dominates(left, right)


def non_dominated_sort(vectors: list[Vector],
                       violations: list[int] | None = None) -> list[list[int]]:
    """Deb's fast non-dominated sort. Returns fronts as lists of indexes, best first.

    Passing `violations` switches to constrained domination.
    """
    if violations is None:
        beats = lambda a, b: dominates(vectors[a], vectors[b])
    else:
        beats = lambda a, b: constrained_dominates(vectors[a], vectors[b],
                                                   violations[a], violations[b])
    count = len(vectors)
    dominated: list[list[int]] = [[] for _ in range(count)]
    incoming = [0] * count
    fronts: list[list[int]] = [[]]

    for p in range(count):
        for q in range(count):
            if p == q:
                continue
            if beats(p, q):
                dominated[p].append(q)
            elif beats(q, p):
                incoming[p] += 1
        if incoming[p] == 0:
            fronts[0].append(p)

    index = 0
    while fronts[index]:
        nxt: list[int] = []
        for p in fronts[index]:
            for q in dominated[p]:
                incoming[q] -= 1
                if incoming[q] == 0:
                    nxt.append(q)
        index += 1
        fronts.append(nxt)
    return fronts[:-1]


def crowding_distance(vectors: list[Vector], front: list[int]) -> dict[int, float]:
    """Spacing around each member, used to prefer spread-out solutions.

    Boundary members get infinite distance so the extremes of the front are never
    discarded; otherwise selection would gradually collapse toward the middle.
    """
    distance = {index: 0.0 for index in front}
    if len(front) <= 2:
        return {index: math.inf for index in front}

    for axis in range(len(vectors[front[0]])):
        ordered = sorted(front, key=lambda i: vectors[i][axis])
        distance[ordered[0]] = math.inf
        distance[ordered[-1]] = math.inf
        low, high = vectors[ordered[0]][axis], vectors[ordered[-1]][axis]
        span = high - low
        if span <= 0:
            continue  # every member ties on this objective; it separates nothing
        for position in range(1, len(ordered) - 1):
            ahead = vectors[ordered[position + 1]][axis]
            behind = vectors[ordered[position - 1]][axis]
            distance[ordered[position]] += (ahead - behind) / span
    return distance
