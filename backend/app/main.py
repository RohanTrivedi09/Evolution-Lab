from __future__ import annotations
import threading, uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .data import list_datasets, load_dataset
from .models import RunRequest, ValidateRequest
from .optimization import Problem, optimizer_for

app = FastAPI(title="Evolution Lab API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
runs: dict[str, dict] = {}
comparisons: dict[str, dict] = {}
cancel_events: dict[str, threading.Event] = {}


class RunCancelled(Exception):
    pass


@app.get("/api/health")
def health(): return {"status":"ok","version":app.version}

@app.get("/api/datasets")
def datasets(): return {"datasets":list_datasets()}

@app.get("/api/datasets/{dataset_id}")
def dataset(dataset_id: str):
    try: return load_dataset(dataset_id).model_dump()
    except KeyError: raise HTTPException(404,"Unknown dataset")

@app.post("/api/datasets/validate")
def validate(request: ValidateRequest): return {"valid":True,"sessions":sum(c.sessions_per_week for c in request.dataset.courses)}

def execute(run_id, request):
    record=runs[run_id]; record["status"]="running"
    try:
        problem=Problem(load_dataset(request.dataset_id))
        def progress(point):
            if cancel_events[run_id].is_set():
                raise RunCancelled()
            record["progress"] = point["iteration"] + 1
            record["latest"] = point
        optimizer=optimizer_for(request.algorithm,problem,request.weights,request.seed,request.parameters,progress); result=optimizer.run()
        if cancel_events[run_id].is_set():
            raise RunCancelled()
        record.update({"status":"completed","result":result.as_dict(problem),"progress":100})
    except RunCancelled:
        record.update({"status":"cancelled"})
    except Exception as exc: record.update({"status":"failed","error":str(exc)})
    finally:
        cancel_events.pop(run_id, None)

@app.post("/api/runs")
def create_run(request: RunRequest):
    try: load_dataset(request.dataset_id)
    except KeyError: raise HTTPException(404,"Unknown dataset")
    run_id=uuid.uuid4().hex; runs[run_id]={"run_id":run_id,"status":"queued","progress":0,"algorithm":request.algorithm,"dataset_id":request.dataset_id,"seed":request.seed,"parameters":request.parameters,"weights":request.weights.model_dump()}
    cancel_events[run_id] = threading.Event()
    threading.Thread(target=execute,args=(run_id,request),daemon=True).start(); return {"run_id":run_id,"status":"queued"}

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    if run_id not in runs: raise HTTPException(404,"Unknown run")
    return runs[run_id]

@app.get("/api/runs/{run_id}/history")
def history(run_id: str):
    if run_id not in runs: raise HTTPException(404,"Unknown run")
    return {"history":runs[run_id].get("result",{}).get("history",[])}

@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str):
    if run_id not in runs: raise HTTPException(404,"Unknown run")
    status = runs[run_id]["status"]
    if status in {"completed", "failed", "cancelled"}:
        return {"status": status}
    cancel_events[run_id].set()
    runs[run_id]["status"]="cancel_requested"; return {"status":"cancel_requested"}

@app.post("/api/comparisons")
def create_comparison(request: RunRequest):
    """Fan out identical framework inputs; only the strategy name differs per child run."""
    comparison_id = uuid.uuid4().hex
    algorithms = ["hill_climbing", "simulated_annealing", "genetic_algorithm", "particle_swarm"]
    child_ids = []
    for algorithm in algorithms:
        child = request.model_copy(update={"algorithm": algorithm})
        child_response = create_run(child)
        child_ids.append(child_response["run_id"])
    comparisons[comparison_id] = {"comparison_id": comparison_id, "status": "running", "run_ids": child_ids}
    return comparisons[comparison_id]

@app.get("/api/comparisons/{comparison_id}")
def get_comparison(comparison_id: str):
    if comparison_id not in comparisons: raise HTTPException(404,"Unknown comparison")
    record = comparisons[comparison_id]
    results = [runs[run_id] for run_id in record["run_ids"]]
    if all(item["status"] in {"completed", "failed", "cancelled"} for item in results): record["status"] = "completed"
    record["runs"] = results
    return record

@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str):
    if run_id not in runs: raise HTTPException(404,"Unknown run")
    return runs[run_id]
