"""The five investigation tools: typed inputs, structured outputs, evidence IDs.

Each tool is a plain function over the World. They summarise on purpose (log
patterns with counts, metric baselines and anomaly onsets) the way real observability
tools do, so an agent spends its tokens on reasoning, not on reading raw lines.

`partial=True` is how the fault injector simulates an incomplete backend answer.
"""

import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from investigator.models import EvidenceItem
from investigator.world import World

UTC_HINT = "ISO 8601 UTC, e.g. 2026-10-03T13:45:00Z"


class ToolInputError(Exception):
    """The arguments are valid JSON but make no sense (unknown service, ...). Not retryable."""


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("start", "end", mode="after", check_fields=False)
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class QueryLogs(ToolInput):
    """Search log lines. Returns message patterns (similar lines grouped, with count and
    first/last seen) plus the most recent matching lines. External vendors have no logs."""

    service: str | None = Field(None, description="Service name; omit for all services")
    level: Literal["ERROR", "WARN", "INFO"] | None = Field(
        None, description="Minimum level (WARN returns WARN and ERROR)"
    )
    contains: str | None = Field(None, description="Case-insensitive text to search for")
    start: datetime | None = Field(None, description=f"Window start, {UTC_HINT}")
    end: datetime | None = Field(None, description=f"Window end, {UTC_HINT}")
    limit: int = Field(12, ge=1, le=40, description="Max raw lines to return (default 12)")


class QueryMetrics(ToolInput):
    """Get a service's metrics: baseline, min/max, detected anomaly (direction, onset,
    peak) and a downsampled series. Omit `metrics` to get all of the service's metrics."""

    service: str
    metrics: list[str] | None = Field(
        None,
        description="e.g. error_rate_pct, latency_p99_ms, rps, cpu_pct, mem_pct, "
        "pod_restarts, connections_active, disk_used_pct, consumer_lag",
    )
    start: datetime | None = Field(None, description=f"Window start, {UTC_HINT}")
    end: datetime | None = Field(None, description=f"Window end, {UTC_HINT}")


class GetDeployments(ToolInput):
    """List changes: deploys, config changes, feature flags, infra changes and campaigns.
    Default window: the 24 hours before now."""

    service: str | None = Field(None, description="Service name; omit for all services")
    kinds: list[Literal["deploy", "config", "feature_flag", "infra", "campaign"]] | None = None
    start: datetime | None = Field(None, description=f"Window start, {UTC_HINT}")
    end: datetime | None = Field(None, description=f"Window end, {UTC_HINT}")


class GetServiceDependencies(ToolInput):
    """Walk the service dependency graph. 'dependencies' = what the service calls,
    'dependents' = who calls it."""

    service: str
    direction: Literal["dependencies", "dependents", "both"] = "both"
    depth: int = Field(2, ge=1, le=3)


class SearchPastIncidents(ToolInput):
    """Search past incident reports by symptoms and services. Similar symptoms do not
    mean the same cause: treat matches as leads to verify, not as evidence."""

    query: str = Field(description="Symptoms or error text to match")
    service: str | None = None
    limit: int = Field(3, ge=1, le=5)


# --- implementations ----------------------------------------------------------------

LEVELS = {"INFO": 0, "WARN": 1, "ERROR": 2}
_ID_LIKE = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{5,}\b")
_NUMBER = re.compile(r"\d+(\.\d+)?")


def _hhmm(ts: datetime) -> str:
    return ts.strftime("%H:%M")


def _window(world: World, start: datetime | None, end: datetime | None) -> tuple[datetime,
                                                                                   datetime]:
    lo = max(start or world.data_start, world.data_start)
    hi = min(end or world.data_end, world.data_end)
    if hi <= lo:
        raise ToolInputError(
            f"Empty window. Data covers {world.data_start.isoformat()} to "
            f"{world.data_end.isoformat()}."
        )
    return lo, hi


def _check_service(world: World, service: str | None) -> None:
    if service is not None and service not in world.service_names:
        raise ToolInputError(
            f"Unknown service {service!r}. Known: {', '.join(world.service_names)}"
        )


def _pattern(message: str) -> str:
    return _NUMBER.sub("<n>", _ID_LIKE.sub("<id>", message))


def query_logs(world: World, args: QueryLogs, partial: bool) -> tuple[dict, list[EvidenceItem]]:
    _check_service(world, args.service)
    lo, hi = _window(world, args.start, args.end)
    min_level = LEVELS[args.level] if args.level else 0
    needle = (args.contains or "").lower()
    matches = [
        ln for ln in world.logs
        if (args.service is None or ln["service"] == args.service)
        and LEVELS[ln["level"]] >= min_level
        and needle in ln["message"].lower()
        and lo <= ln["ts"] < hi
    ]
    note = None
    if partial:
        # One of three log shards did not answer: lose about two thirds of the lines.
        matches = [ln for ln in matches if int(ln["id"][-2:]) % 3 == 0]
        note = "2 of 3 log shards timed out: results are INCOMPLETE (counts are too low)."

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for ln in matches:
        groups.setdefault((ln["service"], ln["level"], _pattern(ln["message"])), []).append(ln)
    ranked = sorted(groups.items(), key=lambda kv: (-LEVELS[kv[0][1]], -len(kv[1])))[:10]
    patterns = [{
        "service": svc, "level": level, "count": len(lines),
        "first_seen": lines[0]["ts"].isoformat(), "last_seen": lines[-1]["ts"].isoformat(),
        "first_id": lines[0]["id"], "example": lines[0]["message"],
    } for (svc, level, _), lines in ranked]
    recent = matches[-args.limit:]

    evidence = [
        EvidenceItem(
            id=p["first_id"], source="logs", service=p["service"],
            ts=datetime.fromisoformat(p["first_seen"]),
            summary=f"{_hhmm(datetime.fromisoformat(p['first_seen']))} {p['service']} "
            f"{p['level']} {p['example'][:160]} (x{p['count']}, first {p['first_seen'][11:16]}"
            f", last {p['last_seen'][11:16]})",
            retrieved_by="",
        )
        for p in patterns
    ] + [
        EvidenceItem(
            id=ln["id"], source="logs", service=ln["service"], ts=ln["ts"],
            summary=f"{_hhmm(ln['ts'])} {ln['service']} {ln['level']} {ln['message'][:160]}",
            retrieved_by="",
        )
        for ln in recent
    ]
    result = {
        "window": [lo.isoformat(), hi.isoformat()],
        "total_matches": len(matches),
        "patterns": patterns,
        "recent_lines": [{"id": ln["id"], "ts": ln["ts"].isoformat(), "service": ln["service"],
                          "level": ln["level"], "message": ln["message"]} for ln in recent],
    }
    if args.service and not matches and not partial:
        result["note"] = "No lines match. Check that this service has logs and the window."
    if note:
        result["note"] = note
    return result, evidence


# Minimum change that counts as an anomaly, per metric (absolute units).
_FLOORS = {"error_rate_pct": 1.0, "pod_restarts": 0.5, "evictions_per_s": 50,
           "consumer_lag": 250, "connections_active": 8}
# Percent-of-capacity metrics: judged in absolute points, not relative to the baseline.
_CAPACITY = {"cpu_pct", "mem_pct", "disk_used_pct", "memory_used_pct"}


def _anomaly(times: list[datetime], values: list[float], base: float, metric: str) -> dict | None:
    spread = statistics.pstdev(values[: max(5, len(values) // 5)]) if len(values) > 5 else 0
    if metric in _CAPACITY:
        threshold = max(4 * spread, 8.0)
    else:
        threshold = max(4 * spread, 0.3 * abs(base), _FLOORS.get(metric, 0.0))
    for i, v in enumerate(values):
        window = values[i: i + 3]
        if (len(window) == 3 and all(abs(x - base) > threshold for x in window)) or (
            metric == "pod_restarts" and v > 0.5
        ):
            direction = "up" if v > base else "down"
            peak_i = (max if direction == "up" else min)(range(i, len(values)),
                                                         key=lambda j: values[j])
            return {"direction": direction, "started_at": times[i].isoformat(),
                    "peak": round(values[peak_i], 2), "peak_at": times[peak_i].isoformat()}
    return None


def query_metrics(world: World, args: QueryMetrics,
                  partial: bool) -> tuple[dict, list[EvidenceItem]]:
    _check_service(world, args.service)
    available = world.metrics.get(args.service)
    if not available:
        raise ToolInputError(f"{args.service} has no metrics (it only emits events/logs).")
    wanted = args.metrics or list(available)
    unknown = [m for m in wanted if m not in available]
    if unknown:
        raise ToolInputError(
            f"Unknown metric(s) {unknown} for {args.service}. Available: {list(available)}"
        )
    lo, hi = _window(world, args.start, args.end)
    step = world.metrics_step
    note = None
    if partial and len(wanted) > 1:
        dropped = wanted[len(wanted) // 2:]
        wanted = wanted[: len(wanted) // 2]
        note = f"Metrics backend returned PARTIAL data: missing {dropped}. Retry for the rest."

    out, evidence = [], []
    for metric in wanted:
        values: list[float] = available[metric]["values"]
        unit = available[metric]["unit"]
        all_times = [world.metrics_start + i * step for i in range(len(values))]
        idx = [i for i, t in enumerate(all_times) if lo <= t < hi]
        ts, vs = [all_times[i] for i in idx], [values[i] for i in idx]
        # Baseline: the 30 minutes before the window if we have them, else its first part.
        before = [values[i] for i in range(len(values)) if lo - timedelta(minutes=30)
                  <= all_times[i] < lo]
        base = statistics.median(before or vs[: max(5, len(vs) // 5)])
        anomaly = _anomaly(ts, vs, base, metric)
        bucket = 5 if len(vs) > 60 else 1
        series = [[_hhmm(ts[i]), round(statistics.fmean(vs[i: i + bucket]), 2)]
                  for i in range(0, len(vs), bucket)]
        entry = {
            "id": f"metric:{args.service}:{metric}", "metric": metric, "unit": unit,
            "baseline": round(base, 2), "min": round(min(vs), 2), "max": round(max(vs), 2),
            "last": round(vs[-1], 2), "anomaly": anomaly, "series": series,
        }
        if metric in _CAPACITY and vs[-1] >= 95:
            entry["saturated"] = True
        out.append(entry)
        u = unit if unit == "%" else f" {unit}"
        if anomaly:
            text = (f"anomaly {anomaly['direction']} from {anomaly['started_at'][11:16]}, "
                    f"peak {anomaly['peak']}{u} at {anomaly['peak_at'][11:16]}")
        else:
            text = "no anomaly in window"
        if entry.get("saturated"):
            text += "; SATURATED (at capacity)"
        evidence.append(EvidenceItem(
            id=entry["id"], source="metrics", service=args.service,
            ts=datetime.fromisoformat(anomaly["started_at"]) if anomaly else None,
            summary=f"{args.service} {metric}: baseline {entry['baseline']}{u}, "
            f"last {entry['last']}{u}; {text} (window {_hhmm(lo)}-{_hhmm(hi)})",
            retrieved_by="",
        ))
    result: dict[str, Any] = {"service": args.service, "window": [lo.isoformat(), hi.isoformat()],
                              "series_step_minutes": bucket if out else None, "metrics": out}
    if note:
        result["note"] = note
    return result, evidence


def get_deployments(world: World, args: GetDeployments,
                    partial: bool) -> tuple[dict, list[EvidenceItem]]:
    _check_service(world, args.service)
    hi = args.end or world.data_end
    lo = args.start or hi - timedelta(hours=24)
    changes = [
        c for c in world.changes
        if (args.service is None or c["service"] == args.service)
        and (args.kinds is None or c["kind"] in args.kinds)
        and lo <= c["ts"] < hi
    ]
    note = None
    if partial and len(changes) > 2:
        changes = changes[: len(changes) // 2]
        note = "Change log returned only the first page: later changes may be MISSING."
    items = [{"id": c["id"], "ts": c["ts"].isoformat(), "service": c["service"],
              "kind": c["kind"], "summary": c["summary"], "author": c["author"],
              "details": c["details"]} for c in changes]
    evidence = [EvidenceItem(
        id=c["id"], source="changes", service=c["service"], ts=c["ts"],
        summary=f"{c['ts'].strftime('%m-%d %H:%M')} {c['kind']} on {c['service']}: "
        f"{c['summary']}" + (f" {c['details']}" if c["details"] else ""),
        retrieved_by="",
    ) for c in changes]
    result: dict[str, Any] = {"window": [lo.isoformat(), hi.isoformat()], "changes": items}
    if note:
        result["note"] = note
    return result, evidence


def get_service_dependencies(world: World, args: GetServiceDependencies,
                             partial: bool) -> tuple[dict, list[EvidenceItem]]:
    _check_service(world, args.service)
    edges = world.topology["edges"]
    depth = 1 if partial else args.depth
    found: dict[str, dict] = {}
    frontier = {args.service}
    for _ in range(depth):
        nxt = set()
        for e in edges:
            down = args.direction in ("dependencies", "both") and e["from"] in frontier
            up = args.direction in ("dependents", "both") and e["to"] in frontier
            if (down or up) and e["id"] not in found:
                found[e["id"]] = e
                nxt.add(e["to"] if down else e["from"])
        frontier = nxt
    involved = {args.service} | {e["from"] for e in found.values()} | {
        e["to"] for e in found.values()}
    services = [s for s in world.topology["services"] if s["name"] in involved]
    evidence = [EvidenceItem(
        id=e["id"], source="topology", service=e["from"], ts=None,
        summary=f"{e['from']} calls {e['to']} ({e['kind']})", retrieved_by="",
    ) for e in found.values()]
    result: dict[str, Any] = {"service": args.service, "edges": list(found.values()),
                              "services": services, "notes": world.topology["notes"]}
    if partial:
        result["note"] = "Graph service degraded: only direct neighbours returned."
    return result, evidence


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "was", "with",
         "since", "from", "after", "not", "no", "are", "be", "by", "at", "users", "user"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def search_past_incidents(world: World, args: SearchPastIncidents,
                          partial: bool) -> tuple[dict, list[EvidenceItem]]:
    query = _words(args.query)
    scored = []
    for h in world.history:
        doc = _words(f"{h['title']} {h['symptoms']} {' '.join(h['services'])}")
        score = len(query & doc) / max(len(query | doc), 1)
        if args.service and args.service in h["services"]:
            score += 0.2
        scored.append((round(score, 3), h))
    scored.sort(key=lambda s: -s[0])
    top = [dict(h, similarity=s) for s, h in scored[: 1 if partial else args.limit] if s > 0]
    evidence = [EvidenceItem(
        id=h["id"], source="history", service=None, ts=None,
        summary=f"past incident {h['date']} '{h['title']}': root cause {h['root_cause']} "
        f"({h['category']})", retrieved_by="",
    ) for h in top]
    result: dict[str, Any] = {"matches": top}
    if partial:
        result["note"] = "Search index degraded: only the top match returned."
    return result, evidence


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input: type[ToolInput]
    run: Callable[[World, Any, bool], tuple[dict, list[EvidenceItem]]]


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec("query_logs", QueryLogs, query_logs),
        ToolSpec("query_metrics", QueryMetrics, query_metrics),
        ToolSpec("get_deployments", GetDeployments, get_deployments),
        ToolSpec("get_service_dependencies", GetServiceDependencies, get_service_dependencies),
        ToolSpec("search_past_incidents", SearchPastIncidents, search_past_incidents),
    ]
}
