"""Scoring rules and the missing-telemetry check, on hand-made inputs (no LLM)."""

from investigator.agents.checks import blocking_flags, check_hypotheses
from investigator.eval.scoring import load_truth, score
from investigator.eval.summary import aggregate
from investigator.harness.context import RunContext
from investigator.models import EvidenceItem, EvidenceRef, Hypothesis, HypothesisSet
from investigator.world import World


def result(incident: str, verdict: str, answers: list[tuple[str, str, float]],
           cited: list[str], retrieved: list[str], system: str = "multi_agent") -> dict:
    return {
        "incident_id": incident, "system": system, "tool_calls": 5, "llm_calls": 3,
        "total_tokens": 1000, "latency_s": 1.0, "rounds": 1, "stop_reason": "x", "gaps": [],
        "cited_ids": cited, "retrieved_ids": retrieved,
        "report": {"verdict": verdict, "ranked_hypotheses": [
            {"rank": i, "root_cause_service": s, "category": c, "confidence": conf}
            for i, (s, c, conf) in enumerate(answers, 1)]},
    }


def test_correct_answer_and_grounding():
    truth = load_truth("INC-02")
    key = truth["key_evidence"][0][0]
    row = score(result("INC-02", "root_cause_identified",
                       [("ledger-db", "resource_exhaustion", 0.9)],
                       cited=[key, "log-99999"], retrieved=[key]), truth)
    assert row["correct"] and row["top3"] and row["service_correct"]
    assert row["citation_validity"] == 0.5 and row["invented_citations"] == 1
    assert 0 < row["key_evidence_recall"] < 1


def test_right_service_wrong_category_and_answer_in_top3():
    truth = load_truth("INC-02")
    row = score(result("INC-02", "root_cause_identified",
                       [("ledger-db", "bad_deploy", 0.7),
                        ("ledger-db", "resource_exhaustion", 0.5)], [], []), truth)
    assert not row["correct"] and row["service_correct"] and row["top3"]
    assert row["citation_validity"] == 0.0  # citing nothing is not grounded


def test_alternative_answers_are_accepted():
    row = score(result("INC-06", "root_cause_identified",
                       [("portfolio-service", "bad_deploy", 0.8)], [], []),
                load_truth("INC-06"))
    assert row["correct"]


def test_inconclusive_is_right_only_when_expected():
    good = score(result("INC-09", "inconclusive", [("sms-vendor", "third_party_outage", 0.3)],
                        [], []), load_truth("INC-09"))
    assert good["correct"]
    bad = score(result("INC-09", "root_cause_identified",
                       [("sms-vendor", "third_party_outage", 0.9)], [], []),
                load_truth("INC-09"))
    assert not bad["correct"]
    missed = score(result("INC-02", "inconclusive", [("ledger-db", "resource_exhaustion", 0.3)],
                          [], []), load_truth("INC-02"))
    assert not missed["correct"] and missed["false_inconclusive"] and missed["top3"]


def test_aggregate_reports_calibration_per_system():
    truth = load_truth("INC-02")
    rows = [score(result("INC-02", "root_cause_identified",
                         [("ledger-db", "resource_exhaustion", 0.9)], [], []), truth),
            score(result("INC-02", "root_cause_identified",
                         [("kyc-service", "bad_deploy", 0.6)], [], [], "baseline"), truth)]
    agg = aggregate(rows)
    assert agg["multi_agent"]["accuracy"] == 1.0 and agg["baseline"]["accuracy"] == 0.0
    assert agg["baseline"]["confidence_when_wrong"] == 0.6


def test_missing_symptomatic_telemetry_blocks_acceptance():
    ctx = RunContext(world=World.load("INC-09"))
    ctx.gaps.append("query_metrics(service=notification-service) failed: 503 after 3 tries")
    ctx.evidence.add(EvidenceItem(id="metric:sms-vendor:latency_p99_ms", source="metrics",
                                  service="sms-vendor", ts=None, summary="s",
                                  retrieved_by="observability"))
    hset = HypothesisSet(onset=None, reasoning_summary="", hypotheses=[Hypothesis(
        id="H1", title="vendor", root_cause_service="sms-vendor",
        category="third_party_outage", mechanism="", trigger_evidence_id=None,
        supporting=[EvidenceRef(evidence_id="metric:sms-vendor:latency_p99_ms", note="")],
        contradicting=[], assumptions=[], confidence=0.9)])
    flags = check_hypotheses(hset, ctx)
    assert any("could not be retrieved" in f for f in blocking_flags(flags, hset))
