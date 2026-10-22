"""Turn scored rows into results/summary.md and results/results.csv."""

import csv
import statistics
from pathlib import Path
from typing import Any

from investigator.eval.scoring import load_truth

SYSTEM_NAMES = {"multi_agent": "Multi-agent", "baseline": "Single-agent baseline"}


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def aggregate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for system in dict.fromkeys(r["system"] for r in rows):
        rs = [r for r in rows if r["system"] == system]
        right = [r["top_confidence"] for r in rs if r["correct"]]
        wrong = [r["top_confidence"] for r in rs if not r["correct"]]
        out[system] = {
            "runs": len(rs),
            "accuracy": _mean([float(r["correct"]) for r in rs]),
            "top3": _mean([float(r["top3"]) for r in rs]),
            "service_accuracy": _mean([float(r["service_correct"]) for r in rs]),
            "false_inconclusive": sum(r["false_inconclusive"] for r in rs),
            "citation_validity": _mean([r["citation_validity"] for r in rs]),
            "invented_citations": sum(r["invented_citations"] for r in rs),
            "key_evidence_recall": _mean([r["key_evidence_recall"] for r in rs]),
            "tool_calls": _mean([r["tool_calls"] for r in rs]),
            "llm_calls": _mean([r["llm_calls"] for r in rs]),
            "tokens": _mean([r["tokens"] for r in rs]),
            "tokens_total": sum(r["tokens"] for r in rs),
            "latency_s": _mean([r["latency_s"] for r in rs]),
            "latency_p50_s": statistics.median([r["latency_s"] for r in rs]),
            "rate_limit_wait_s": _mean([r["rate_limit_wait_s"] for r in rs]),
            "latency_ex_waits_s": _mean([r["latency_ex_waits_s"] for r in rs]),
            "confidence_when_right": _mean(right),
            "confidence_when_wrong": _mean(wrong),
        }
    return out


def _fmt(value: Any, kind: str = "") -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value:.0%}"
    if kind == "int":
        return f"{value:,.0f}"
    if kind == "s":
        return f"{value:.1f}s"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


METRICS = [
    ("Root-cause accuracy (top-1)", "accuracy", "pct"),
    ("Correct answer in top 3", "top3", "pct"),
    ("Right service (any category)", "service_accuracy", "pct"),
    ("Wrongly said inconclusive", "false_inconclusive", "int"),
    ("Citation validity (cited IDs really retrieved)", "citation_validity", "pct"),
    ("Invented citations (total)", "invented_citations", "int"),
    ("Key-evidence recall", "key_evidence_recall", "pct"),
    ("Tool calls per incident (incl. retries)", "tool_calls", ""),
    ("LLM calls per incident", "llm_calls", ""),
    ("Tokens per incident", "tokens", "int"),
    ("Tokens, all incidents", "tokens_total", "int"),
    ("Latency per incident (mean)", "latency_s", "s"),
    ("Latency per incident (median)", "latency_p50_s", "s"),
    ("  of which waiting on rate limits (mean)", "rate_limit_wait_s", "s"),
    ("Latency without rate-limit waits (mean)", "latency_ex_waits_s", "s"),
    ("Mean top confidence when right", "confidence_when_right", ""),
    ("Mean top confidence when wrong", "confidence_when_wrong", ""),
]


def _cell(r: dict[str, Any]) -> str:
    answer = "inconclusive" if r["verdict"] == "inconclusive" else r["top_answer"]
    return (f"{'✅' if r['correct'] else '❌'} {answer} ({r['top_confidence']:.2f}), "
            f"{r['tool_calls']} tools, {r['tokens']:,} tok, {r['latency_s']:.0f}s")


def write_summary(rows: list[dict[str, Any]], out: Path, *, title: str, notes: list[str]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    agg = aggregate(rows)
    systems = list(agg)
    lines = [f"# {title}", "", *notes, "", "## Overall", "",
             "| Metric | " + " | ".join(SYSTEM_NAMES.get(s, s) for s in systems) + " |",
             "|---|" + "---|" * len(systems)]
    for label, key, kind in METRICS:
        lines.append(f"| {label} | " + " | ".join(_fmt(agg[s][key], kind) for s in systems)
                     + " |")
    lines += ["", f"Runs per system: {', '.join(f'{s}={agg[s]['runs']}' for s in systems)}.",
              "", "## Per incident", "",
              "| Incident | Expected | " + " | ".join(SYSTEM_NAMES.get(s, s) for s in systems)
              + " |", "|---|---|" + "---|" * len(systems)]
    for incident in dict.fromkeys(r["incident"] for r in rows):
        cells = []
        for s in systems:
            rs = [r for r in rows if r["incident"] == incident and r["system"] == s]
            cells.append("<br>".join(_cell(r) for r in rs) or "-")
        expected = next(r["expected"] for r in rows if r["incident"] == incident)
        lines.append(f"| {incident} | {expected} | " + " | ".join(cells) + " |")
    lines += ["", "## Traps per incident", ""]
    for incident in dict.fromkeys(r["incident"] for r in rows):
        truth = load_truth(incident)
        lines.append(f"- **{incident}**: {'; '.join(truth['traps'])}")
    path = out / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
