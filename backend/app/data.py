from pathlib import Path
import json
from .models import Dataset

DATA_DIR = Path(__file__).parent / "data"


def load_dataset(dataset_id: str) -> Dataset:
    path = DATA_DIR / f"{dataset_id}.json"
    if not path.exists():
        raise KeyError(dataset_id)
    return Dataset.model_validate(json.loads(path.read_text()))


def list_datasets() -> list[dict]:
    result = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = Dataset.model_validate(json.loads(path.read_text()))
        result.append({"id": path.stem, "name": data.name, "description": data.description, "courses": len(data.courses)})
    return result

