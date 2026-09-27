import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "sample-data" / "incidents"

def load_incident(incident_id: str) -> dict:
    p = DATA_DIR / f"{incident_id}.json"
    if not p.exists():
        raise SystemExit(f"Unknown incident: {incident_id}")
    return json.loads(p.read_text(encoding="utf-8"))
