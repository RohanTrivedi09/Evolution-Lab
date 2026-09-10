"""Evolution Lab API: application assembly only. Behaviour lives in api/ and services/."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_datasets, routes_runs, routes_schedule

app = FastAPI(title="Evolution Lab API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(routes_datasets.router)
app.include_router(routes_runs.router)
app.include_router(routes_schedule.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": app.version}
