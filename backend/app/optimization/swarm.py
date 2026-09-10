"""Discrete Particle Swarm Optimization.

Timetables are not continuous, so this is a documented adaptation rather than
textbook PSO. A particle's "velocity" is a set of per-gene adoption probabilities:

    c2  chance of copying the swarm best's placement for that session
    c1  chance of copying the particle's own best placement
    w   chance of applying one random neighbourhood move (exploration)

Attraction that is too strong collapses swarm diversity early - which the diversity
metric in the history makes visible.
"""
from __future__ import annotations

import time

from .base import Optimizer, OptimizationResult


class ParticleSwarm(Optimizer):
    name = "particle_swarm"

    def run(self) -> OptimizationResult:
        started = time.perf_counter()
        size = max(2, int(self.params.get("swarm_size", 20)))
        inertia = float(self.params.get("w", 0.2))
        cognitive = float(self.params.get("c1", 0.25))
        social = float(self.params.get("c2", 0.35))

        seed_candidate = self.initial_candidate()
        particles = [seed_candidate] + [
            self.problem.random_candidate(self.rng) for _ in range(size - 1)
        ]
        personal = []
        for particle in particles:
            if self.budget_exhausted():
                break
            personal.append(([a.copy() for a in particle], self.score(particle)))
        particles = particles[:len(personal)]
        if not personal:
            candidate = self.problem.random_candidate(self.rng)
            return self.finish(candidate, self.score(candidate), started)

        global_best = min(personal, key=lambda entry: entry[1].total_cost)
        global_best = ([a.copy() for a in global_best[0]], global_best[1])
        initial_cost = global_best[1].total_cost

        iteration = 0
        while not self.budget_exhausted():
            adoptions = 0
            for index, particle in enumerate(particles):
                if self.budget_exhausted():
                    break
                for gene in range(len(particle)):
                    roll = self.rng.random()
                    if roll < social:
                        particle[gene] = global_best[0][gene].copy()
                        adoptions += 1
                    elif roll < social + cognitive:
                        particle[gene] = personal[index][0][gene].copy()
                        adoptions += 1
                if self.rng.random() < inertia:
                    # Assign back into the swarm: a rebind here would discard exploration.
                    particle = self.mutate(particle)
                    particles[index] = particle

                score = self.score(particle)
                if score.total_cost < personal[index][1].total_cost:
                    personal[index] = ([a.copy() for a in particle], score)
                if score.total_cost < global_best[1].total_cost:
                    global_best = ([a.copy() for a in particle], score)

            iteration += 1
            average = sum(score.total_cost for _, score in personal) / len(personal)
            diversity = len({self.problem.fingerprint(p) for p in particles})
            converged = 100 * (1 - global_best[1].total_cost / max(1.0, initial_cost))
            self.record(iteration, global_best[1], global_best[0], average=average, force=True,
                        event="Particles drawn toward personal and swarm bests",
                        particle_count=len(particles),
                        swarm_diversity=diversity,
                        average_velocity=round(adoptions / max(1, len(particles) * len(global_best[0])), 3),
                        convergence_percentage=round(max(0.0, converged), 2),
                        inertia=inertia, c1=cognitive, c2=social)

        return self.finish(global_best[0], global_best[1], started)
