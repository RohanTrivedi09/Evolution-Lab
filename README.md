# Evolution Lab

Evolution Lab is a comparative timetable optimization playground. All algorithms use the same dataset model, candidate representation, evaluator, metrics, run API, and UI visualization pipeline; only the optimization strategy varies.

## Run locally

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Run backend tests with `cd backend && pytest`.

While a run is active, `GET /api/runs/{run_id}` exposes the latest evaluated
schedule in `latest.schedule`; the frontend renders that snapshot as it
changes. Active runs can be stopped with `POST /api/runs/{run_id}/cancel`.
