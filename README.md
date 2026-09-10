# Evolution Lab

A comparative timetable optimization playground. Every algorithm shares one dataset
model, one candidate representation, one evaluator, one result contract and one
visualization pipeline — only the search strategy differs.

## Run locally

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Tests: `cd backend && pytest` (119 tests).

## Fair comparison

Algorithms are compared on a shared budget of **fitness evaluations**, not iterations.
One hill-climbing iteration costs one evaluation; one GA generation costs a whole
population. Comparing on iterations therefore compares budgets, not strategies.

- `max_evaluations` on a run request sets the budget (default 2000).
- `POST /api/comparisons` gives **every** strategy the same budget.
- Convergence charts plot cost against evaluations for the same reason.
- Legacy `parameters.iterations` / `generations` are still translated into a budget, so
  older requests behave as before.

Every fitness call goes through `Optimizer.score()`, which is what makes the reported
evaluation count trustworthy. The evaluator is a free function rather than a method on
`Problem`, so there is no convenient way to score a candidate off the books.

## What it does

**Lab** (`#/lab`) — run one strategy or race all four, edit the resulting timetable and
hand it back to be repaired, study behaviour across repeated seeds, and change what the
objective cares about.

- **Equal-budget racing.** Every strategy spends the same number of fitness evaluations.
- **Repeated-seed study.** Mean, standard deviation, best, feasibility rate, seed wins
  and evaluations-to-first-feasible. A single seed is an anecdote.
- **Editable timetable.** Drag a lecture, or focus one and use the arrow keys. The move
  is scored by the same evaluator the optimizers use, so the number shown is the number
  they would see, and "Repair from here" continues the search from your edit.
- **Objective weights.** Raise gaps to buy compact days at the cost of preferences.
  Weights cannot go negative; that would make the search maximise clashes.
- **Fuzzy comfort model.** A crisp/fuzzy toggle, described below.
- **Paste your own dataset.** Validated with field-level errors and runnable immediately.
- **Export.** JSON report, CSV timetable, or the browser's print view.

## Fuzzy inference

Soft Computing spans fuzzy, neural and evolutionary methods; the optimizers cover the
evolutionary half. `weights.fuzzy` switches the comfort term to a Mamdani inference
system: congestion, fragmentation and edge load are fuzzified into low/medium/high, run
through a five-rule base (min for AND, max for OR), aggregated by max and defuzzified by
centroid.

The point is not decoration. Crisp penalties force a hard line where human judgement has
none — nobody believes two idle periods is exactly twice as bad as one. It is off by
default so earlier results stay comparable, and it changes only the comfort term: hard
constraints stay dominant, which is asserted directly in the tests.

`GET /api/fuzzy/profile` serves the membership curves and rule base, and every fuzzy
score carries the inputs, their memberships and which rules fired with what strength.

## Story mode

`#/story` is a scroll-driven walkthrough that doubles as the demo script: the problem's
scale, then each strategy in turn, then a head-to-head on the shared budget.

The mechanic is scrubbing — scroll position inside a scene maps to an index in that
run's history, so the reader drives the optimization forward with the scrollbar instead
of watching a timer replay it. Hill Climbing visibly stalls and restarts; Simulated
Annealing's temperature and acceptance probability collapse; the GA's diversity falls;
the swarm converges.

`#/lab` is the original dashboard, untouched by the story.

Story runs are cached in `sessionStorage`, so scrolling back up never refetches. The
story stretches the cooling schedule (`cooling_rate` 0.994) across its 1,200-evaluation
budget: the 0.95 default is tuned for a ~100-iteration run and would flatten to zero in
the first tenth of the scroll.

Under `prefers-reduced-motion` the scenes collapse to their natural height and render
their final state, because scroll-linked movement is what that preference asks us to
avoid.

## Layout

```
backend/app/
  models.py                 Pydantic schemas for datasets, runs and edits
  data.py                   Sample dataset loading
  optimization/
    representation.py       Session, Assignment, Problem, the candidate domain
    evaluator.py            The shared fitness function: 7 hard, 6 soft constraints
    neighborhood.py         move / swap / change-room operators, shared by all searches
    base.py                 Budget accounting, history recording, trajectory sampling
    local_search.py         Hill Climbing, Simulated Annealing
    genetic.py              GA with uniform / one-point crossover and cached fitness
    swarm.py                Discrete PSO (documented adaptation, not continuous PSO)
  services/run_manager.py   Run lifecycle, cancellation, expiry
  api/                      routes_datasets, routes_runs, routes_schedule
```

```
frontend/src/
  types.ts                  Shared API types
  api/client.ts             Typed fetch wrappers
  components/TimetableGrid  Week grid: every session in a slot, conflicts badged
  lab/Lab.tsx               The dashboard
  story/                    Scene (scroll scrubbing) + Story (the narrative)
  styles/story.css
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service status |
| `GET /api/datasets` · `GET /api/datasets/{id}` | Sample datasets |
| `POST /api/datasets/validate` | Validate a pasted dataset, with field-level errors |
| `POST /api/datasets` | Store a pasted dataset for this session and return its id |
| `POST /api/runs` | Start a run (`max_evaluations`, optional `initial_schedule`) |
| `GET /api/runs/{id}` | Status, progress, live best, final result |
| `GET /api/runs/{id}/history` · `/trajectory` · `/export` | Charts, search path, download |
| `POST /api/runs/{id}/cancel` | Cooperative cancellation |
| `POST /api/comparisons` · `GET /api/comparisons/{id}` | Equal-budget four-way race |
| `POST /api/schedule/evaluate` | Score a hand-edited timetable without running a search |
| `POST /api/experiments` · `GET /api/experiments/{id}` | Repeated-seed study across algorithms |
| `GET /api/fuzzy/profile` | Membership curves and the fuzzy rule base |

`initial_schedule` starts a search from a supplied timetable, so a user edit can be
handed to an algorithm to repair. `POST /api/schedule/evaluate` scores an edit with the
same evaluator the optimizers use, so the UI never reimplements the fitness function.

While a run is active, `GET /api/runs/{id}` exposes the latest evaluated schedule in
`latest.schedule`; the frontend renders that snapshot as it changes.

## Input limits

Spec section 7 requires uploaded input to be size-limited, because a pasted dataset can
expand into millions of sessions before anything looks wrong. Collections are capped
(14 days, 24 periods, 200 rooms, 500 faculty, 200 groups, 500 courses) and a dataset may
expand to at most 2,000 sessions. Pasted datasets are held in memory, bounded to the 20
most recent, and never touch disk; a dataset id cannot address anything outside the data
directory.

Scoring refuses an incomplete schedule rather than completing it: inventing the missing
placements would report their collisions as the caller's own.

## Results

`docs/experiment-results.md` records the measured comparisons, how to reproduce them,
and a threats-to-validity section covering the dataset assumptions.

## Known limitations

- `Course.duration` is parsed but not yet used; every session occupies one period.
- Runs, experiments and pasted datasets are held in memory — nothing survives a restart.
- `evaluations_to_feasible` is the first *recorded* feasible point; history is decimated
  to about 200 points, so it is approximate.
- The bundled `adani-sem7-cse` dataset assumes group sizes and room capacities that the
  source timetables do not state, and models no faculty unavailability.
- Discrete PSO is an adaptation: "velocity" is a set of per-gene adoption
  probabilities (`w`, `c1`, `c2`), documented in `optimization/swarm.py`.
