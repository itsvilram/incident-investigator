"""The synthetic dataset is consistent, and the answers stay out of the tools' reach."""

import json

import pytest

from investigator.world import DATA_ROOT, World, list_incidents

INCIDENTS = list_incidents()


def load_truth(incident_id: str) -> dict:
    return json.loads((DATA_ROOT / "ground_truth" / f"{incident_id}.json").read_text())


def test_at_least_ten_incidents_with_every_trap_type():
    assert len(INCIDENTS) >= 10
    truths = [load_truth(i) for i in INCIDENTS]
    assert any(t["verdict"] == "inconclusive" for t in truths)
    worlds = [World.load(i) for i in INCIDENTS]
    assert sum(1 for w in worlds if w.faults) >= 3  # tool failures are part of the test set


@pytest.mark.parametrize("incident_id", INCIDENTS)
def test_world_loads_and_is_coherent(incident_id):
    world = World.load(incident_id)
    names = set(world.service_names)
    assert set(world.incident.symptom_services) <= names
    assert {ln["service"] for ln in world.logs} <= names
    assert {c["service"] for c in world.changes} <= names
    assert [ln["ts"] for ln in world.logs] == sorted(ln["ts"] for ln in world.logs)
    assert world.data_start < world.incident.reported_at < world.data_end


@pytest.mark.parametrize("incident_id", INCIDENTS)
def test_key_evidence_exists_in_the_world(incident_id):
    world = World.load(incident_id)
    truth = load_truth(incident_id)
    ids = {ln["id"] for ln in world.logs} | {c["id"] for c in world.changes}
    ids |= {f"metric:{s}:{m}" for s, metrics in world.metrics.items() for m in metrics}
    for group in truth["key_evidence"]:
        assert group, "an empty evidence group can never be covered"
        assert set(group) <= ids
    if truth["verdict"] == "identified":
        assert truth["root_cause_service"] in world.service_names


def test_world_files_do_not_contain_the_answers():
    for incident_id in INCIDENTS:
        folder = DATA_ROOT / "world" / "incidents" / incident_id
        text = " ".join(p.read_text() for p in folder.iterdir())
        truth = load_truth(incident_id)
        assert truth["explanation"][:40] not in text
        assert "ground_truth" not in text
