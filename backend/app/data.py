"""Dataset loading: the bundled samples plus anything pasted in this session."""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from .models import Dataset

DATA_DIR = Path(__file__).parent / "data"
MAX_UPLOADS = 20

# Pasted datasets live in memory for the session. Storing them behind an id rather than
# threading a whole dataset through every request keeps one seam: runs, comparisons,
# experiments and scoring all keep taking a dataset_id and need no change.
_uploaded: dict[str, Dataset] = {}
_lock = threading.Lock()


def register_dataset(dataset: Dataset) -> str:
    dataset_id = f"pasted-{uuid.uuid4().hex[:8]}"
    with _lock:
        while len(_uploaded) >= MAX_UPLOADS:
            _uploaded.pop(next(iter(_uploaded)))
        _uploaded[dataset_id] = dataset
    return dataset_id


def load_dataset(dataset_id: str) -> Dataset:
    with _lock:
        pasted = _uploaded.get(dataset_id)
    if pasted is not None:
        return pasted
    path = DATA_DIR / f"{dataset_id}.json"
    # Reject anything that escapes the data directory before touching the filesystem.
    if "/" in dataset_id or "\\" in dataset_id or not path.is_file():
        raise KeyError(dataset_id)
    return Dataset.model_validate(json.loads(path.read_text()))


def _summary(dataset_id: str, data: Dataset, pasted: bool) -> dict:
    return {"id": dataset_id, "name": data.name or dataset_id,
            "description": data.description, "courses": len(data.courses),
            "sessions": sum(c.sessions_per_week for c in data.courses), "pasted": pasted}


def list_datasets() -> list[dict]:
    result = [_summary(path.stem, Dataset.model_validate(json.loads(path.read_text())), False)
              for path in sorted(DATA_DIR.glob("*.json"))]
    with _lock:
        result.extend(_summary(key, data, True) for key, data in _uploaded.items())
    return result
