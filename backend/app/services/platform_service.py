import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "sample-data"


class PlatformService:
    """Reads the non-incident reference data: catalog, alerts, on-call, workflows, status page."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def _read(self, *parts: str):
        return json.loads((self.data_dir.joinpath(*parts)).read_text(encoding="utf-8"))

    def catalog(self) -> dict:
        return self._read("catalog", "catalog.json")

    def alerts(self) -> dict:
        return self._read("alerts", "alerts.json")

    def oncall(self) -> dict:
        return self._read("oncall", "oncall.json")

    def workflows(self) -> list:
        return self._read("workflows", "workflows.json")

    def status_page(self) -> dict:
        return self._read("status-page", "status-page.json")
