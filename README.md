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

Tests: `cd backend && pytest` (64 tests).

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
| `POST /api/runs` | Start a run (`max_evaluations`, optional `initial_schedule`) |
| `GET /api/runs/{id}` | Status, progress, live best, final result |
| `GET /api/runs/{id}/history` · `/trajectory` · `/export` | Charts, search path, download |
| `POST /api/runs/{id}/cancel` | Cooperative cancellation |
| `POST /api/comparisons` · `GET /api/comparisons/{id}` | Equal-budget four-way race |
| `POST /api/schedule/evaluate` | Score a hand-edited timetable without running a search |

`initial_schedule` starts a search from a supplied timetable, so a user edit can be
handed to an algorithm to repair. `POST /api/schedule/evaluate` scores an edit with the
same evaluator the optimizers use, so the UI never reimplements the fitness function.

While a run is active, `GET /api/runs/{id}` exposes the latest evaluated schedule in
`latest.schedule`; the frontend renders that snapshot as it changes.

## Known limitations

- `Course.duration` is parsed but not yet used; every session occupies one period.
- Runs are held in memory with a TTL — there is no persistence across restarts.
- Discrete PSO is an adaptation: "velocity" is a set of per-gene adoption
  probabilities (`w`, `c1`, `c2`), documented in `optimization/swarm.py`.
