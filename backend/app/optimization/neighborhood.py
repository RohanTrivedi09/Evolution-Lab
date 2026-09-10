"""Move operators shared by every local and population-based search.

Hill Climbing, Simulated Annealing, the GA's mutation step and PSO's exploration all
draw from this module, so a "neighbour" means the same thing for all of them.
"""
from __future__ import annotations

import random

from .representation import Candidate, Problem


def move_session(problem: Problem, candidate: Candidate, rng: random.Random) -> Candidate:
    """Relocate one session to a different slot and room."""
    child = [a.copy() for a in candidate]
    index = rng.randrange(len(child))
    child[index] = problem.random_assignment(rng)
    return child


def swap_sessions(problem: Problem, candidate: Candidate, rng: random.Random) -> Candidate:
    """Exchange the placements of two sessions."""
    child = [a.copy() for a in candidate]
    if len(child) < 2:
        return move_session(problem, candidate, rng)
    left, right = rng.sample(range(len(child)), 2)
    child[left], child[right] = child[right], child[left]
    return child


def change_room(problem: Problem, candidate: Candidate, rng: random.Random) -> Candidate:
    """Keep the time slot, move the session to another room."""
    child = [a.copy() for a in candidate]
    index = rng.randrange(len(child))
    child[index].room = rng.choice(problem.room_ids)
    return child


OPERATORS = (move_session, swap_sessions, change_room)
OPERATOR_NAMES = {operator: operator.__name__ for operator in OPERATORS}


def random_neighbor(problem: Problem, candidate: Candidate,
                    rng: random.Random) -> tuple[Candidate, str]:
    """Apply one uniformly chosen operator. Returns the neighbour and the operator used."""
    operator = rng.choice(OPERATORS)
    return operator(problem, candidate, rng), operator.__name__
