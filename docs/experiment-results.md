# Experimental results

All figures below were produced by the code in this repository and can be reproduced
with the commands shown. Every comparison uses one shared budget of **fitness
evaluations**, because an iteration costs a different amount of work in each strategy:
one hill-climbing iteration is a single evaluation, one genetic generation is a whole
population. Comparing on iterations compares budgets, not strategies.

## Datasets

| Dataset | Courses | Sessions/week | Rooms | Faculty | Groups | Slots per session |
|---|---:|---:|---:|---:|---:|---:|
| `small-college` | 6 | 9 | 3 | 3 | 2 | 75 |
| `medium-college` | 6 | 13 | 5 | 4 | 3 | 175 |
| `adani-sem7-cse` | 48 | 85 | 19 | 12 | 9 | 760 |

`adani-sem7-cse` is transcribed from the real Semester VII CSE (AI-ML) timetables for
sections A, B and C, effective 03/08/2026. Its search space is roughly 10^245.

## Single race, equal budget

`adani-sem7-cse`, 20,000 evaluations each, seed 42:

| Algorithm | Cost | Hard violations | Group gaps | Runtime |
|---|---:|---:|---:|---:|
| Simulated annealing | 3,920 | 0 | 22 | 8.0 s |
| Particle swarm | 9,140 | 0 | 49 | 9.1 s |
| Genetic algorithm | 10,920 | 0 | 69 | 10.5 s |
| Hill climbing | 44,300 | **3** | 84 | 9.4 s |

Hill climbing never reaches a feasible timetable: three clashes survive the budget.

## Repeated seeds

A single seed is an anecdote. Five seeds, 3,000 evaluations each, `adani-sem7-cse`:

| Algorithm | Mean | Std dev | Best | Feasible | Seed wins | Evals to feasible |
|---|---:|---:|---:|---:|---:|---:|
| Simulated annealing | 9,443 | 417 | 8,945 | 100% | 5/5 | 1,776 |
| Hill climbing | 78,615 | 5,263 | 73,740 | 0% | 0/5 | never |
| Particle swarm | 154,210 | 43,102 | 96,175 | 0% | 0/5 | never |
| Genetic algorithm | 207,789 | 16,503 | 178,670 | 0% | 0/5 | never |

**The budget, not the strategy alone, decides.** At 3,000 evaluations only annealing
reaches feasibility at all; at 20,000 three of the four do. Any claim of the form
"algorithm X beats algorithm Y" is meaningless without stating the budget.

Particle swarm has by far the widest spread (std 43,102), which is the diversity
collapse its own telemetry reports: strong attraction converges quickly but the landing
place depends heavily on where the swarm started.

On the small dataset all four reach feasibility and finish within 300-500, which is why
a realistic instance matters: the toy set cannot separate them.

## Reproducing

```bash
cd backend
.venv/bin/python -m pytest -q                 # 109 tests

# single race
curl -s -X POST localhost:8000/api/comparisons \
  -H 'content-type: application/json' \
  -d '{"dataset_id":"adani-sem7-cse","max_evaluations":20000}'

# repeated-seed study
curl -s -X POST localhost:8000/api/experiments \
  -H 'content-type: application/json' \
  -d '{"dataset_id":"adani-sem7-cse","seed_count":5,"max_evaluations":3000}'
```

Runs with the same dataset, parameters and seed are reproducible; this is asserted per
algorithm in `tests/test_algorithms.py`.

## Threats to validity

- **Capacity is not enforced.** The source timetables state no room sizes and no batch
  sizes, so rather than score invented values the constraint was removed. Six hard
  constraints are evaluated, not the seven in spec section 8. Results below therefore say
  nothing about whether rooms are large enough.
- **Faculty unavailability is not modelled.** The timetables record where each member
  teaches, not when they are free. Deriving unavailability from the published placements
  would be circular: it would feed the existing answer back in as a constraint.
- **Labs are modelled as single periods.** The real labs are two-hour blocks;
  `Course.duration` is parsed but unused.
- **Evaluations to first feasible is approximate.** History is decimated to about 200
  points, so the figure is the first *recorded* feasible point, not the exact evaluation.
- **Parameters are defaults**, not tuned per algorithm. A tuned GA would likely close
  much of its gap; these numbers compare out-of-the-box behaviour at equal budget.
- **Five seeds is few.** The standard deviations are wide enough that the ordering of
  the three infeasible strategies should not be treated as settled.
