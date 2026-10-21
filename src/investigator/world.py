"""Load one incident's synthetic world (what the tools can see).

Ground truth lives in data/ground_truth/ and is deliberately not loaded here:
nothing an agent can reach knows the answer.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from investigator.models import IncidentReport

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class FaultRule:
    """A scripted tool failure: the first `times` matching calls fail with `mode`."""

    tool: str
    mode: str  # timeout | error | partial
    times: int
    service: str | None = None


@dataclass
class World:
    incident: IncidentReport
    logs: list[dict]  # each has id, ts (datetime), service, level, message
    metrics_start: datetime
    metrics_step: timedelta
    metrics: dict[str, dict[str, dict]]  # service -> metric -> {"unit", "values"}
    changes: list[dict]  # each has id, ts (datetime), service, kind, summary, author, details
    topology: dict
    history: list[dict]
    faults: list[FaultRule] = field(default_factory=list)

    @property
    def data_start(self) -> datetime:
        return self.metrics_start

    @property
    def data_end(self) -> datetime:
        n = max(len(m["values"]) for svc in self.metrics.values() for m in svc.values())
        return self.metrics_start + n * self.metrics_step

    @property
    def service_names(self) -> list[str]:
        return [s["name"] for s in self.topology["services"]]

    @classmethod
    def load(cls, incident_id: str, root: Path = DATA_ROOT) -> "World":
        base = root / "world" / "incidents" / incident_id
        if not base.is_dir():
            raise FileNotFoundError(f"No incident {incident_id} under {base.parent}")
        incident = IncidentReport.model_validate_json((base / "incident.json").read_text())
        logs = []
        for line in (base / "logs.jsonl").read_text().splitlines():
            entry = json.loads(line)
            entry["ts"] = datetime.fromisoformat(entry["ts"])
            logs.append(entry)
        metrics = json.loads((base / "metrics.json").read_text())
        changes = json.loads((base / "changes.json").read_text())
        for ch in changes:
            ch["ts"] = datetime.fromisoformat(ch["ts"])
        faults = [FaultRule(**f) for f in json.loads((base / "faults.json").read_text())]
        return cls(
            incident=incident,
            logs=logs,
            metrics_start=datetime.fromisoformat(metrics["start"]),
            metrics_step=timedelta(seconds=metrics["step_seconds"]),
            metrics=metrics["services"],
            changes=changes,
            topology=json.loads((base / "topology.json").read_text()),
            history=json.loads((root / "world" / "history.json").read_text()),
            faults=faults,
        )


def list_incidents(root: Path = DATA_ROOT) -> list[str]:
    return sorted(p.name for p in (root / "world" / "incidents").iterdir() if p.is_dir())
