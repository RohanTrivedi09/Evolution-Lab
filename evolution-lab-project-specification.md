# Evolution Lab: A Comparative Soft Computing Optimization Playground

## 1. Project Overview

**Evolution Lab** is an interactive web application for solving and comparing college timetable scheduling problems with multiple soft computing algorithms. Users provide a small academic scheduling dataset, choose an algorithm, configure parameters, run optimization, and observe how candidate solutions improve over time.

The project is deliberately built as a comparative playground rather than a single-purpose timetable generator. It demonstrates how different optimization strategies behave on the same problem:

- Hill Climbing
- Simulated Annealing
- Genetic Algorithm
- Particle Swarm Optimization
- Optional multi-objective optimization extensions

The final system should make the algorithms understandable through visual evidence: fitness curves, timetable snapshots, constraint violations, parameter controls, and side-by-side comparisons.

**Primary academic domain:** Soft Computing and computational optimization  
**Application domain:** College course timetable scheduling  
**Expected duration:** 3–4 weeks  
**Recommended team size:** 2–4 students

## 2. Motivation

Creating a timetable manually is difficult because several requirements must be satisfied simultaneously. A schedule may need to avoid faculty clashes, room conflicts, student-group overlaps, unavailable periods, room-capacity violations, and undesirable gaps. These requirements can conflict, and the search space grows rapidly with the number of classes, rooms, and time slots.

Traditional exhaustive search becomes impractical for realistic instances. Soft computing is appropriate because it searches for high-quality, near-optimal solutions under uncertainty and competing objectives. The project provides a concrete way to explain:

1. how a real problem is encoded as a search space;
2. how different algorithms explore that space;
3. how a fitness function expresses practical preferences;
4. why no single algorithm is best for every dataset;
5. how optimization quality and computational cost can be compared experimentally.

## 3. Objectives

### Primary objectives

- Model college timetable scheduling as a constrained optimization problem.
- Implement Hill Climbing, Simulated Annealing, Genetic Algorithm, and Particle Swarm Optimization.
- Use a common evaluation framework so algorithms can be compared fairly.
- Provide a FastAPI backend for optimization jobs and results.
- Provide a React frontend with interactive controls and visualizations.
- Explain algorithm behavior using generation/iteration history rather than only showing the final timetable.
- Produce reproducible experiments using fixed random seeds.

### Secondary objectives

- Support weighted preferences in addition to hard constraints.
- Support at least two timetable objectives, such as minimizing violations and minimizing student gaps.
- Display trade-offs between schedule quality and runtime.
- Make the project suitable for a live academic demonstration.

## 4. Mapping to Syllabus Topics

| Syllabus topic | Project application | Evidence in the demo |
|---|---|---|
| Evolutionary computing | General search framework, populations, variation, selection, and adaptation | Algorithm comparison and optimization history |
| Hill climbing | Local search over neighboring timetable states | Improvement path and local-optimum behavior |
| Simulated annealing | Controlled acceptance of worse states using a cooling schedule | Temperature curve and accepted-move history |
| Genetic algorithms | Population-based search using selection, crossover, and mutation | Generation best/average fitness and chromosome evolution |
| Multi-objective optimization | Separate hard-violation, preference, and gap objectives; optional Pareto ranking | Pareto scatter plot and selectable schedules |
| Particle swarm optimization | Population of candidate schedules with velocity-inspired movement or discrete swap operators | Particle fitness and swarm convergence |
| Fitness functions | Quantitative measure of timetable quality | Constraint breakdown and weighted score |
| Comparative experimentation | Same dataset, budget, and evaluation metrics for every algorithm | Comparison dashboard |

## 5. Scope and Assumptions

### In scope

- One institution, one timetable, one academic week.
- A configurable set of days and periods.
- Lectures, labs, rooms, faculty, student groups, and availability data.
- Small and medium demonstration datasets.
- Single-run optimization and batch comparison runs.
- JSON API and browser-based visualizations.

### Out of scope for the minimum viable project

- Authentication and user accounts.
- Persistent multi-tenant deployment.
- Automatic data import from a university ERP.
- Guaranteed mathematical optimality.
- Complex cross-semester or cross-campus constraints.

## 6. Functional Requirements

### Dataset management

The system shall:

- ship with at least two sample datasets: a small demo dataset and a larger stress-test dataset;
- allow users to upload or paste a validated JSON dataset;
- validate references between courses, faculty, rooms, groups, and availability;
- show a human-readable validation error when input is invalid;
- allow users to select a random seed.

### Problem configuration

Users shall be able to configure:

- algorithm;
- iteration or generation budget;
- population/swarm size where applicable;
- mutation and crossover rates for GA;
- initial temperature and cooling rate for SA;
- neighborhood size for local search;
- objective weights;
- whether soft preferences are enabled.

### Optimization execution

The backend shall:

- create an optimization run;
- return a run identifier;
- execute the selected algorithm with a common interface;
- expose progress and completed results;
- support cancellation where practical;
- return the best schedule, score, constraint breakdown, runtime, and history.

### Results and comparison

The frontend shall:

- render a timetable grid for a selected solution;
- show hard and soft constraint violations separately;
- show best-so-far and average fitness over time;
- compare algorithms on the same dataset;
- allow selecting a run to inspect its detailed history;
- export a result as JSON and a printable timetable view.

## 7. Non-Functional Requirements

- **Correctness:** Hard constraints must be evaluated consistently across all algorithms.
- **Reproducibility:** A run with the same dataset, parameters, and seed should produce the same result, subject to documented parallelism behavior.
- **Usability:** A first-time user should be able to run a sample experiment in under two minutes.
- **Performance:** A small dataset should complete interactively, ideally within 5 seconds for a normal demonstration budget.
- **Observability:** Every run should record parameters, seed, duration, evaluations, and algorithm history.
- **Maintainability:** Algorithms must be replaceable through a shared optimizer interface.
- **Safety:** Uploaded input must be size-limited and schema-validated; no arbitrary code or file paths should be accepted.
- **Testability:** Fitness evaluation and constraint handling must be testable independently of the UI.
- **Accessibility:** Use readable contrast, keyboard-accessible controls, labels, and non-color indicators for violations.

## 8. Timetable Problem Definition

### Input model

Represent a problem using the following logical entities:

```json
{
  "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
  "periods": ["09:00", "10:00", "11:00", "13:00", "14:00"],
  "rooms": [
    {"id": "R101", "capacity": 60, "type": "lecture"},
    {"id": "LAB1", "capacity": 40, "type": "lab"}
  ],
  "faculty": [
    {"id": "F01", "name": "Dr. Rao", "unavailable": [{"day": "Fri", "period": "14:00"}]}
  ],
  "groups": [{"id": "CSE-A", "size": 48}],
  "courses": [
    {
      "id": "CS301",
      "name": "Soft Computing",
      "faculty_id": "F01",
      "group_ids": ["CSE-A"],
      "sessions_per_week": 2,
      "duration": 1,
      "room_type": "lecture",
      "preferred_periods": [{"day": "Tue", "period": "10:00"}]
    }
  ]
}
```

Expand each course into session instances before optimization. For example, a course with two weekly sessions becomes `CS301-1` and `CS301-2`.

### Candidate schedule

Each session is assigned:

```text
(day_index, period_index, room_id)
```

Example:

```json
{
  "CS301-1": {"day": "Tue", "period": "10:00", "room_id": "R101"},
  "CS301-2": {"day": "Thu", "period": "11:00", "room_id": "R101"}
}
```

### Hard constraints

Hard constraints should be treated as violations with a very large penalty, or repaired immediately when a repair operation is available.

1. No faculty member teaches two sessions at the same time.
2. No student group attends two sessions at the same time.
3. No room hosts two sessions at the same time.
4. Room capacity must satisfy group size.
5. Room type must match course requirements.
6. Faculty unavailable periods cannot be used.
7. A session must be placed within the valid day/period domain.

### Soft constraints

Soft constraints express preferences and should contribute smaller penalties:

1. Avoid undesirable faculty periods.
2. Minimize gaps in a group’s day.
3. Avoid unnecessary first/last-period classes.
4. Spread repeated sessions across different days.
5. Prefer a faculty member’s requested periods.
6. Minimize room changes for a group where possible.

## 9. Fitness Function

Use a shared score so every algorithm evaluates solutions identically. Lower is better internally; the UI may display a normalized higher-is-better score.

```text
total_cost =
    W_HARD * hard_violations
  + W_SOFT * soft_violations
  + W_GAP * student_group_gaps
  + W_FRAGMENTATION * daily_fragmentation
```

Recommended initial weights:

```text
W_HARD = 10,000
W_SOFT = 100
W_GAP = 10
W_FRAGMENTATION = 5
```

The evaluator should return a structured breakdown:

```json
{
  "total_cost": 123.0,
  "normalized_fitness": 0.87,
  "hard_violations": 0,
  "soft_violations": 4,
  "group_gaps": 6,
  "daily_fragmentation": 3,
  "violation_details": []
}
```

The exact weights must be configurable and documented. Avoid hiding all behavior inside one opaque score.

## 10. Representations and Algorithm Design

### 10.1 Hill Climbing

- **State:** One complete timetable represented as an array of session assignments.
- **Neighbor:** Move one session to another valid slot/room, swap two sessions, or change only the room.
- **Selection:** Best-improvement or first-improvement search.
- **Stopping:** Maximum iterations, no improvement for a patience window, or zero hard violations plus target score.
- **Teaching point:** Fast local improvement but vulnerable to local optima and plateaus.

### 10.2 Simulated Annealing

- **State:** One complete timetable using the same representation as Hill Climbing.
- **Neighbor:** Use the same move operators for a fair comparison.
- **Acceptance:** Always accept improvements; sometimes accept worse moves according to `exp(-delta / temperature)`.
- **Cooling:** `temperature = temperature * cooling_rate` after each iteration.
- **Teaching point:** Can escape local optima early, then becomes increasingly selective.

### 10.3 Genetic Algorithm

- **Chromosome:** Ordered list of assignments, one gene per session.
- **Population:** A collection of chromosomes, preferably initialized with a mixture of random and lightly repaired schedules.
- **Selection:** Tournament selection or rank selection.
- **Crossover:** One-point or uniform crossover over session genes, followed by repair.
- **Mutation:** Move one gene, swap two genes, or replace a room assignment.
- **Elitism:** Preserve the best small percentage of each generation.
- **Teaching point:** Maintains population diversity and searches multiple regions simultaneously.

### 10.4 Particle Swarm Optimization

PSO is naturally continuous, so this project should use a documented discrete adaptation.

- **Particle position:** A complete timetable chromosome.
- **Particle velocity:** A weighted list of swap/move operations, or a probability of applying each operation.
- **Personal best:** Best timetable found by a particle.
- **Global best:** Best timetable found by the swarm.
- **Movement:** Generate candidate schedules by combining operations that move the particle toward its personal and global best, then apply random exploration.
- **Teaching point:** Information sharing across a population can produce rapid convergence, but excessive attraction can reduce diversity.

If the discrete PSO becomes unreliable, retain it as an experimental extension and clearly report the adaptation rather than presenting it as standard continuous PSO.

### 10.5 Multi-objective extension

The minimum implementation may use a weighted sum. A stronger extension maintains separate objectives:

- minimize hard violations;
- minimize soft preference penalties;
- minimize student gaps;
- minimize room utilization imbalance.

Implement Pareto dominance and display non-dominated solutions in a scatter plot. The user should be able to select a Pareto solution and inspect its timetable.

## 11. Architecture

```text
React frontend
  ├── Dataset/configuration controls
  ├── Run controls and progress state
  ├── Timetable grid
  ├── Fitness/constraint charts
  └── Comparison dashboard
          │ REST/JSON
FastAPI backend
  ├── API routers
  ├── Pydantic schemas
  ├── Run manager
  ├── Common optimizer interface
  ├── Algorithm implementations
  ├── Fitness and constraint evaluator
  └── Sample datasets
          │
  In-memory run store for MVP
  Optional SQLite persistence for stretch goal
```

The backend should isolate domain logic from HTTP routes. The frontend should consume stable API schemas and should not reimplement fitness calculations.

## 12. Technology Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, Uvicorn.
- **Algorithms:** Python standard library first; NumPy may be used for numeric utilities if helpful.
- **Testing:** Pytest, HTTP client tests for API behavior.
- **Frontend:** React with Vite and TypeScript.
- **Visualization:** Recharts, Plotly, or another well-maintained React charting library.
- **Styling:** CSS modules, plain CSS, or a lightweight component library.
- **Data exchange:** JSON over REST.
- **Development:** Git, `.env.example`, README, and reproducible local startup commands.

Avoid adding a database, job queue, or cloud infrastructure before the core algorithms and visualizations work.

## 13. API Endpoints

### `GET /api/health`

Returns service status and version.

### `GET /api/datasets`

Returns available sample datasets and metadata.

### `GET /api/datasets/{dataset_id}`

Returns a complete sample dataset.

### `POST /api/datasets/validate`

Validates a submitted dataset without running an optimizer.

### `POST /api/runs`

Creates and starts an optimization run.

Example request:

```json
{
  "dataset_id": "small-college",
  "algorithm": "genetic_algorithm",
  "seed": 42,
  "parameters": {
    "generations": 100,
    "population_size": 40,
    "mutation_rate": 0.12,
    "crossover_rate": 0.8
  },
  "weights": {
    "hard": 10000,
    "soft": 100,
    "gaps": 10
  }
}
```

Returns `{ "run_id": "...", "status": "queued" }`.

### `GET /api/runs/{run_id}`

Returns status, parameters, progress, current best score, and final result when complete.

### `GET /api/runs/{run_id}/history`

Returns iteration/generation history for charts.

### `POST /api/runs/{run_id}/cancel`

Requests cancellation of an active run.

### `POST /api/comparisons`

Runs multiple algorithms on the same dataset and returns a comparison identifier.

### `GET /api/comparisons/{comparison_id}`

Returns run summaries, rankings, and data needed for the dashboard.

### `GET /api/runs/{run_id}/export`

Returns the result as downloadable JSON. A printable HTML or CSV export may be added later.

## 14. Visualization Requirements

The visualization layer is a core part of the project, not decoration.

### Timetable view

- Day columns and period rows.
- Course, faculty, room, and group shown in each cell.
- Hard-conflict cells visibly marked.
- Tooltips or an expandable panel for full session details.
- Clear empty-period styling.

### Optimization progress

- Best fitness versus iteration/generation.
- Average fitness for population-based algorithms.
- Hard-violation count versus iteration/generation.
- For SA, temperature versus iteration and accepted-worse-move count.
- For GA, diversity proxy or unique chromosome count where available.

### Constraint breakdown

- Hard violations by category.
- Soft penalties by category.
- Before/after comparison when an initial schedule is available.

### Algorithm comparison

- Summary cards for best score, hard violations, runtime, and evaluations.
- Overlaid convergence curves.
- Box plot or table across repeated seeds where batch mode is implemented.
- Highlight the recommended solution while allowing users to inspect all runs.

## 15. Comparison Dashboard

The dashboard should support a fair experiment protocol:

1. Select one dataset.
2. Select two or more algorithms.
3. Apply an equal evaluation budget where possible.
4. Use the same fitness weights and constraints.
5. Run each algorithm with one or more seeds.
6. Compare final quality, feasibility, runtime, and convergence.

Recommended comparison table:

| Algorithm | Best cost | Hard violations | Soft penalties | Runtime | Evaluations | Feasible? |
|---|---:|---:|---:|---:|---:|---|
| Hill Climbing | — | — | — | — | — | — |
| Simulated Annealing | — | — | — | — | — | — |
| Genetic Algorithm | — | — | — | — | — | — |
| Particle Swarm | — | — | — | — | — | — |

The dashboard must not rank algorithms using runtime alone. A schedule with zero hard violations should normally outrank a faster schedule with severe conflicts.

## 16. Sample Datasets

### Dataset A: Small demo

- 5 days, 5 periods per day.
- 6–8 courses.
- 3 rooms, including one lab.
- 3 faculty members.
- 2 student groups.
- Designed to complete quickly and visibly improve during a live demo.

### Dataset B: Medium classroom

- 5 days, 7 periods per day.
- 15–20 courses.
- 6–8 rooms, including lecture rooms and labs.
- 8–10 faculty members.
- 4–6 student groups.
- Includes availability restrictions and repeated sessions.

### Dataset C: Stress test

- 5 or 6 days, 8 periods per day.
- 30+ courses.
- 10+ rooms and multiple resource types.
- Dense conflicts and tighter availability.
- Used to demonstrate scalability and algorithm differences.

Each dataset should have a human-readable description and a known validation status. Do not hard-code assumptions that only work for Dataset A.

## 17. Implementation Plan by Milestone

### Milestone 1 — Project foundation and data model

- Create backend and frontend skeletons.
- Define dataset schemas and sample JSON files.
- Implement dataset validation.
- Implement session expansion and slot utilities.
- Add health and dataset endpoints.
- Add basic frontend dataset selector.

**Exit criterion:** A sample dataset loads in the browser and passes validation.

### Milestone 2 — Evaluator and baseline schedule

- Implement timetable representation.
- Implement all hard-constraint checks.
- Implement soft penalties and score breakdown.
- Generate a random baseline schedule.
- Add evaluator unit tests.
- Render the baseline timetable and constraint breakdown.

**Exit criterion:** The same candidate schedule receives the same detailed score from every caller.

### Milestone 3 — Hill Climbing and Simulated Annealing

- Define shared optimizer result and history models.
- Implement neighborhood operators.
- Implement Hill Climbing.
- Implement Simulated Annealing.
- Add run endpoints and progress polling.
- Add convergence charts.

**Exit criterion:** Both algorithms complete a run and visibly improve the baseline on the small dataset.

### Milestone 4 — Genetic Algorithm and PSO

- Implement GA population, selection, crossover, mutation, repair, and elitism.
- Implement documented discrete PSO adaptation.
- Add population-specific history metrics.
- Add algorithm parameter controls.

**Exit criterion:** All four algorithms use the same evaluator and return compatible result objects.

### Milestone 5 — Comparison dashboard and polish

- Implement multi-algorithm comparison endpoint.
- Add side-by-side metrics and convergence overlays.
- Add export functionality.
- Add loading, error, empty, and cancellation states.
- Improve labels, legends, accessibility, and demo flow.

**Exit criterion:** A complete comparison can be run from a clean checkout using documented commands.

### Optional Milestone 6 — Multi-objective extension

- Add separate objective vectors.
- Implement Pareto dominance.
- Display a Pareto front.
- Allow selection and inspection of a non-dominated timetable.

## 18. Recommended Folder Structure

```text
evolution-lab/
├── README.md
├── PROJECT_SPEC.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes_datasets.py
│   │   │   ├── routes_runs.py
│   │   │   └── routes_comparisons.py
│   │   ├── models/
│   │   │   ├── dataset.py
│   │   │   ├── run.py
│   │   │   └── result.py
│   │   ├── optimization/
│   │   │   ├── base.py
│   │   │   ├── representation.py
│   │   │   ├── evaluator.py
│   │   │   ├── neighborhood.py
│   │   │   ├── hill_climbing.py
│   │   │   ├── simulated_annealing.py
│   │   │   ├── genetic_algorithm.py
│   │   │   └── particle_swarm.py
│   │   ├── services/
│   │   │   └── run_manager.py
│   │   └── data/
│   │       ├── small-college.json
│   │       ├── medium-college.json
│   │       └── stress-college.json
│   └── tests/
│       ├── test_validation.py
│       ├── test_evaluator.py
│       ├── test_algorithms.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── charts/
│   │   ├── types/
│   │   └── App.tsx
│   └── public/
└── docs/
    ├── experiment-results.md
    └── screenshots/
```

## 19. Evaluation Metrics

Evaluate algorithms using both solution quality and search behavior:

- final total cost;
- hard-constraint violation count;
- soft-constraint penalty;
- number of student-group gaps;
- runtime;
- number of fitness evaluations;
- iterations/generations to first feasible schedule;
- best-so-far cost at fixed budget checkpoints;
- convergence stability across random seeds;
- solution diversity for population-based methods.

For a meaningful report, run each algorithm at least five times on the same dataset when time permits. Report mean, best, and standard deviation. State all parameter values and seeds.

## 20. Testing Strategy

### Unit tests

- Valid and invalid dataset schemas.
- Session expansion.
- Slot and room compatibility.
- Each hard constraint independently.
- Each soft penalty independently.
- Score weighting and normalized fitness.
- Neighbor generation preserves valid domains.
- Crossover and mutation preserve chromosome length.
- Optimizer stopping conditions.

### Integration tests

- Create a run through the API.
- Poll until completion.
- Retrieve history and final timetable.
- Compare two algorithms on one dataset.
- Handle invalid input and unknown run IDs.

### Frontend tests

- Dataset selection and configuration state.
- Loading/error/empty states.
- Timetable rendering.
- Chart rendering with missing or partial history.
- Comparison table sorting and result selection.

### Manual checks

- Run the complete demo from a clean environment.
- Resize the browser and check timetable readability.
- Verify that conflict indicators are not conveyed by color alone.
- Confirm repeated runs with the same seed are reproducible.

## 21. Demo Script

1. Introduce the problem: manually building a timetable requires satisfying competing constraints.
2. Load the small college dataset and show the input entities.
3. Display a random baseline schedule and its conflicts.
4. Run Hill Climbing and point out rapid early improvement and possible stagnation.
5. Run Simulated Annealing and show temperature decreasing while occasional worse moves are accepted.
6. Run the Genetic Algorithm and explain chromosome, population, crossover, mutation, and elitism.
7. Run PSO and explain the discrete timetable adaptation and swarm information sharing.
8. Open the comparison dashboard and compare feasibility, score, runtime, and convergence.
9. Change the weights to prioritize fewer student gaps or faculty preferences.
10. If implemented, show the Pareto front and select two schedules with different trade-offs.
11. Conclude that soft computing does not merely produce one answer; it helps explore good answers under competing goals.

## 22. Estimated Timeline: 3–4 Weeks

| Period | Deliverables |
|---|---|
| Days 1–3 | Repository setup, schemas, datasets, API skeleton |
| Days 4–7 | Representation, evaluator, baseline timetable, tests |
| Week 2 | Hill Climbing, Simulated Annealing, first charts |
| Week 3 | Genetic Algorithm, PSO, run management, frontend controls |
| Week 4 | Comparison dashboard, experiments, polish, documentation, final demo |

If only three weeks are available, defer Pareto optimization, persistence, and advanced export. Do not defer evaluator tests or the basic comparison view.

## 23. Stretch Goals

- Pareto-front multi-objective optimization.
- Interactive manual editing followed by re-optimization.
- WebSocket progress updates instead of polling.
- SQLite result history.
- CSV and printable PDF export.
- More neighborhood operators and repair heuristics.
- Constraint toggles for teaching experiments.
- Algorithm parameter presets such as “fast,” “balanced,” and “deep search.”
- Experiment notebook or automatic report generation.
- Deployment using Docker.

## 24. Instructions for Codex

This section is the implementation contract for an AI coding agent working on the project.

### Implementation priorities

1. Build a runnable vertical slice first: sample dataset → evaluator → one optimizer → API → timetable UI.
2. Keep the evaluator independent from all algorithms and the HTTP layer.
3. Add Hill Climbing and Simulated Annealing before population-based algorithms so the basic pipeline is verified early.
4. Implement GA next, with explicit chromosome operators and tests for length/domain preservation.
5. Implement PSO as a clearly documented discrete adaptation; do not silently claim it is continuous PSO.
6. Add comparison and visual polish only after all algorithms return a common result schema.
7. Prefer deterministic seeded randomness in tests and demo presets.
8. Keep algorithm parameters visible in the UI and record them with every run.
9. Return structured violation details so the frontend can explain why a schedule scored poorly.
10. Preserve a clean README with exact startup, test, and demo commands.

### Engineering rules

- Use type hints in Python and TypeScript types in the frontend.
- Use Pydantic models for all API input and output boundaries.
- Do not duplicate fitness formulas in the frontend.
- Do not use global mutable state for active runs unless it is encapsulated in a run manager.
- Avoid blocking the API event loop for long optimization jobs; use a simple background execution strategy appropriate for an MVP.
- Make cancellation cooperative at iteration/generation boundaries.
- Add tests with every algorithm, not only after the entire UI is built.
- Keep the default dataset small enough for a live demo.
- Treat hard constraints as dominant over soft preferences.
- Document every non-standard design choice, especially discrete PSO and repair logic.

### Definition of done

The project is ready for submission when:

- all four algorithms run through the same API;
- the small dataset produces a complete timetable and score breakdown;
- the UI displays convergence and comparison metrics;
- tests cover validation, evaluator logic, algorithm invariants, and main API paths;
- repeated seeded runs are reproducible;
- the README explains setup and demo steps;
- the final report includes algorithm mapping, design decisions, evaluation results, screenshots, and limitations.

### Suggested first coding task

Start by creating the backend schemas, the small sample dataset, the timetable representation, and a fully tested evaluator. Add a random baseline endpoint or service before implementing optimization. This establishes the shared contract that every later algorithm and visualization will use.

## 25. Expected Final Deliverables

- Source code for backend and frontend.
- This project specification and an implementation README.
- At least two sample datasets.
- Automated tests and test results.
- Screenshots or a short recording of the dashboard.
- Experimental comparison across algorithms and seeds.
- Final presentation/demo script.
- A short report explaining the soft computing concepts demonstrated, design trade-offs, results, and limitations.

