"""Score one investigation against the ground truth. The only code that reads answers."""

import json
from typing import Any

from investigator.world import DATA_ROOT


def load_truth(incident_id: str) -> dict[str, Any]:
    return json.loads((DATA_ROOT / "ground_truth" / f"{incident_id}.json").read_text())


def score(result: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """`result` is RunResult.to_json(). Returns one flat row for the results table."""
    report = result["report"]
    ranked = sorted(report["ranked_hypotheses"], key=lambda h: h["rank"])
    answers = [(h["root_cause_service"], h["category"]) for h in ranked]
    top = answers[0] if answers else (None, None)
    accepted = {tuple(a) for a in truth["accepted"]}
    said_inconclusive = report["verdict"] == "inconclusive"

    if truth["verdict"] == "inconclusive":
        correct = top3 = service_correct = said_inconclusive
    else:
        correct = not said_inconclusive and top in accepted
        top3 = any(a in accepted for a in answers[:3])
        service_correct = top[0] in {a[0] for a in accepted}

    cited = result["cited_ids"]
    retrieved = set(result["retrieved_ids"])
    groups = truth["key_evidence"]
    return {
        "incident": result["incident_id"],
        "system": result["system"],
        "expected": ("inconclusive" if truth["verdict"] == "inconclusive"
                     else f"{truth['root_cause_service']} / {truth['category']}"),
        "verdict": report["verdict"],
        "top_answer": f"{top[0]} / {top[1]}" if top[0] else "-",
        "top_confidence": ranked[0]["confidence"] if ranked else 0.0,
        "correct": correct,
        "top3": top3,
        "service_correct": service_correct,
        "false_inconclusive": truth["verdict"] != "inconclusive" and said_inconclusive,
        # A report that cites nothing is not grounded at all.
        "citation_validity": (sum(c in retrieved for c in cited) / len(cited)) if cited else 0.0,
        "invented_citations": sum(c not in retrieved for c in cited),
        "key_evidence_recall": (sum(any(i in cited for i in g) for g in groups) / len(groups)
                                if groups else None),
        "tool_calls": result["tool_calls"],
        "llm_calls": result["llm_calls"],
        "tokens": result["total_tokens"],
        "latency_s": result["latency_s"],
        "rounds": result["rounds"],
        "stop_reason": result["stop_reason"],
        "gaps": len(result["gaps"]),
    }
