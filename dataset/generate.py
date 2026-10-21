"""Expand the scenarios into the synthetic world the tools read.

    uv run python dataset/generate.py

Writes, per incident:
    data/world/incidents/<ID>/incident.json   the report the system receives
    data/world/incidents/<ID>/logs.jsonl      background noise + scenario lines
    data/world/incidents/<ID>/metrics.json    1-minute series per service and metric
    data/world/incidents/<ID>/changes.json    7 days of deploys/config/flags + scenario changes
    data/world/incidents/<ID>/topology.json   services and dependency edges
    data/world/incidents/<ID>/faults.json     tool failures to inject (harness only)
    data/world/history.json                   past incidents (shared)
    data/ground_truth/<ID>.json               the answer: only the scorer reads this

Everything is seeded per incident, so the output is the same on every run.
"""

import json
import random
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenarios import HISTORY, SCENARIOS, Scenario

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "data" / "world"
TRUTH = ROOT / "data" / "ground_truth"

DATA_START = "12:00"  # logs and metrics start here; they end shortly after the report
AFTER_REPORT_MIN = 10

# name: (kind, owner, base rps, base p99 ms). kind decides metrics and log style.
SERVICES: dict[str, tuple[str, str, float, float]] = {
    "mobile-bff": ("api", "app-platform", 1150, 420),
    "auth-service": ("api", "identity", 140, 220),
    "payments-api": ("api", "payments", 260, 380),
    "upi-gateway": ("api", "payments", 210, 450),
    "ledger-service": ("api", "ledger", 300, 120),
    "fraud-service": ("api", "risk", 260, 60),
    "portfolio-service": ("api", "investing", 380, 300),
    "orders-service": ("api", "investing", 120, 350),
    "market-data-service": ("api", "investing", 900, 40),
    "kyc-service": ("api", "identity", 25, 600),
    "aa-connector": ("api", "growth", 18, 900),
    "notification-service": ("api", "engagement", 160, 250),
    "user-db": ("db", "platform-data", 900, 12),
    "ledger-db": ("db", "platform-data", 1400, 15),
    "portfolio-db": ("db", "platform-data", 600, 10),
    "redis-cache": ("cache", "platform-data", 4200, 2),
    "redis-session": ("cache", "platform-data", 700, 2),
    "event-bus": ("queue", "platform-data", 520, 6),
    "coredns": ("platform", "platform", 3100, 3),
    "kubernetes": ("events", "platform", 0, 0),
    "otp-provider": ("external", "vendor: SMS OTP", 60, 900),
    "npci-switch": ("external", "NPCI", 210, 300),
    "partner-bank-api": ("external", "partner bank", 210, 350),
    "broker-api": ("external", "broker", 110, 280),
    "market-feed": ("external", "exchange feed", 50, 120),
    "kyc-vendor": ("external", "vendor: KYC", 25, 700),
    "aa-fiu-gateway": ("external", "AA network", 18, 650),
    "sms-vendor": ("external", "vendor: SMS", 90, 600),
    "push-provider": ("external", "vendor: push", 120, 300),
}

EDGES: list[tuple[str, str, str]] = [  # (caller, callee, kind)
    ("mobile-bff", "auth-service", "sync"),
    ("mobile-bff", "payments-api", "sync"),
    ("mobile-bff", "portfolio-service", "sync"),
    ("mobile-bff", "orders-service", "sync"),
    ("mobile-bff", "kyc-service", "sync"),
    ("mobile-bff", "aa-connector", "sync"),
    ("auth-service", "user-db", "sync"),
    ("auth-service", "redis-session", "sync"),
    ("auth-service", "otp-provider", "sync"),
    ("payments-api", "ledger-service", "sync"),
    ("payments-api", "upi-gateway", "sync"),
    ("payments-api", "fraud-service", "sync"),
    ("payments-api", "redis-cache", "sync"),
    ("payments-api", "event-bus", "async"),
    ("upi-gateway", "npci-switch", "sync"),
    ("upi-gateway", "partner-bank-api", "sync"),
    ("ledger-service", "ledger-db", "sync"),
    ("fraud-service", "redis-cache", "sync"),
    ("portfolio-service", "portfolio-db", "sync"),
    ("portfolio-service", "market-data-service", "sync"),
    ("orders-service", "broker-api", "sync"),
    ("orders-service", "portfolio-db", "sync"),
    ("market-data-service", "market-feed", "sync"),
    ("market-data-service", "redis-cache", "sync"),
    ("kyc-service", "kyc-vendor", "sync"),
    ("kyc-service", "user-db", "sync"),
    ("aa-connector", "aa-fiu-gateway", "sync"),
    ("aa-connector", "user-db", "sync"),
    ("notification-service", "event-bus", "async"),
    ("notification-service", "sms-vendor", "sync"),
    ("notification-service", "push-provider", "sync"),
]

PLATFORM_NOTES = [
    "coredns is the cluster DNS: every service resolves hostnames through it (not shown as edges).",
    "kubernetes is the cluster control plane; its events (OOM kills, restarts, scaling) are "
    "logged under service 'kubernetes'.",
    "External services (kind=external) have no logs of ours; their metrics come from "
    "synthetic probes plus our clients' call stats.",
]

COMMON = ["rps", "error_rate_pct", "latency_p99_ms"]
METRICS_BY_KIND = {
    "api": [*COMMON, "cpu_pct", "mem_pct", "pod_restarts"],
    "db": [*COMMON, "cpu_pct", "mem_pct", "connections_active", "disk_used_pct"],
    "cache": [*COMMON, "cpu_pct", "memory_used_pct", "evictions_per_s"],
    "queue": [*COMMON, "cpu_pct", "consumer_lag"],
    "platform": [*COMMON, "cpu_pct", "mem_pct"],
    "external": COMMON,
    "events": [],
}
UNITS = {
    "rps": "req/s", "error_rate_pct": "%", "latency_p99_ms": "ms", "cpu_pct": "%",
    "mem_pct": "%", "pod_restarts": "restarts/min", "connections_active": "connections",
    "disk_used_pct": "%", "memory_used_pct": "%", "evictions_per_s": "keys/s",
    "consumer_lag": "messages",
}

BACKGROUND_LOGS = {
    "api": [
        ("INFO", "GET /v1/{path} 200 in {fast}ms"),
        ("INFO", "POST /v1/{path} 201 in {fast}ms"),
        ("INFO", "health check ok"),
        ("WARN", "slow request GET /v1/{path} took {slow}ms"),
        ("WARN", "retrying call to {dep} (attempt 1 of 3)"),
    ],
    "db": [
        ("INFO", "checkpoint complete: wrote {n} buffers"),
        ("INFO", "automatic vacuum of table \"{table}\": index scans: 1"),
        ("INFO", "connection authorized: user=app database=main"),
    ],
    "cache": [("INFO", "Background saving started"), ("INFO", "DB saved on disk")],
    "queue": [("INFO", "Committed offsets for group {group}")],
    "platform": [("INFO", "[INFO] plugin/reload: configuration unchanged")],
    "events": [("INFO", "Scaled deployment {svc} replicas unchanged"),
               ("INFO", "Pod {svc}-{h} readiness probe ok")],
}
PATHS = ["payments/intent", "holdings", "orders", "profile", "accounts", "sip", "receipts"]
TABLES = ["ledger_entries", "users", "holdings", "orders", "sessions"]
GROUPS = ["notif-alerts", "ledger-events", "fraud-signals"]

ROUTINE_CHANGES = [
    ("deploy", "v{v}: dependency bumps"),
    ("deploy", "v{v}: logging improvements"),
    ("deploy", "v{v}: minor bug fixes"),
    ("config", "raise request timeout 5s -> 6s"),
    ("config", "rotate API credentials (scheduled)"),
    ("feature_flag", "enable new_onboarding_copy for 20% of users"),
    ("infra", "node pool patch: kernel security update"),
]


def at(day: str, hhmm: str) -> datetime:
    """'13:52' or '-1d 18:20' on the scenario's day, as an aware UTC datetime."""
    base = datetime.fromisoformat(day).replace(tzinfo=UTC)
    offset = 0
    if hhmm.startswith("-"):
        days, hhmm = hhmm.split(" ")
        offset = int(days[1:-1])
    h, m = (int(x) for x in hhmm.split(":"))
    return base - timedelta(days=offset) + timedelta(hours=h, minutes=m)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def fill(template: str, rng: random.Random, svc: str) -> str:
    deps = [b for a, b, _ in EDGES if a == svc] or ["upstream"]
    values = {
        "n": str(rng.randint(3, 900)), "ms": str(rng.randint(1200, 9800)),
        "id": f"{rng.getrandbits(32):08x}", "p": str(rng.randint(90, 99)),
        "h": f"{rng.getrandbits(20):05x}", "path": rng.choice(PATHS),
        "slow": str(rng.randint(1100, 2500)), "fast": str(rng.randint(15, 450)),
        "dep": rng.choice(deps),
        "table": rng.choice(TABLES), "group": rng.choice(GROUPS), "svc": rng.choice(
            [s for s, v in SERVICES.items() if v[0] == "api"]),
    }
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


def baseline(svc: str, metric: str, rng: random.Random) -> float:
    kind, _, rps, p99 = SERVICES[svc]
    return {
        "rps": rps, "latency_p99_ms": p99,
        "error_rate_pct": 0.05 if kind in ("db", "cache", "queue", "platform") else 0.3,
        "cpu_pct": rng.uniform(25, 42), "mem_pct": rng.uniform(48, 62),
        "pod_restarts": 0.0, "connections_active": 45.0, "disk_used_pct": rng.uniform(55, 68),
        "memory_used_pct": rng.uniform(45, 60), "evictions_per_s": 0.0, "consumer_lag": 120.0,
    }[metric]


def jitter(metric: str, value: float, rng: random.Random) -> float:
    if metric in ("pod_restarts", "evictions_per_s") and value == 0:
        return 0.0
    if metric == "error_rate_pct":
        return max(0.0, value + rng.gauss(0, max(0.08, value * 0.06)))
    if metric in ("disk_used_pct", "connections_active"):
        return max(0.0, value + rng.gauss(0, 0.4))
    return max(0.0, value * (1 + rng.gauss(0, 0.05)))


def build_metrics(sc: Scenario, start: datetime, minutes: int, rng: random.Random) -> dict:
    series: dict[str, dict[str, list[float]]] = {}
    for svc, (kind, *_rest) in SERVICES.items():
        series[svc] = {}
        for metric in METRICS_BY_KIND[kind]:
            base = baseline(svc, metric, rng)
            values = []
            for i in range(minutes):
                # a gentle daily curve on traffic so the series are not flat lines
                curve = 1 + 0.08 * ((i / minutes) - 0.5) if metric == "rps" else 1
                values.append(base * curve)
            series[svc][metric] = values

    for eff in sc.metrics:
        values = series[eff.service][eff.metric]
        i0 = int((at(sc.day, eff.at) - start).total_seconds() // 60)
        i_end = int((at(sc.day, eff.end) - start).total_seconds() // 60) if eff.end else minutes
        base = eff.start_value if eff.start_value is not None else values[max(i0 - 1, 0)]
        if eff.shape == "ramp":
            i_full = int((at(sc.day, eff.until or eff.at) - start).total_seconds() // 60)
            for i in range(max(i0, 0), min(i_end, minutes)):
                frac = 1.0 if i >= i_full else (i - i0) / max(i_full - i0, 1)
                values[i] = base + (eff.value - base) * frac
        elif eff.shape == "pulse":
            for i in range(max(i0, 0), min(i_end, minutes)):
                values[i] = eff.value if (i - i0) % eff.every == 0 else 0.0
        else:
            for i in range(max(i0, 0), min(i_end, minutes)):
                values[i] = eff.value

    return {
        "start": iso(start), "step_seconds": 60,
        "services": {
            svc: {
                m: {"unit": UNITS[m], "values": [round(jitter(m, v, rng), 2) for v in vals]}
                for m, vals in metrics.items()
            }
            for svc, metrics in series.items() if metrics
        },
    }


def build_logs(sc: Scenario, start: datetime, end: datetime, rng: random.Random):
    lines: list[dict] = []
    keyed: list[tuple[dict, str]] = []
    blackout = {svc: at(sc.day, t) for svc, t in sc.log_blackout}

    for svc, (kind, *_rest) in SERVICES.items():
        templates = BACKGROUND_LOGS.get(kind)
        if not templates:
            continue  # external services: no logs of ours
        ts = start + timedelta(seconds=rng.randint(0, 120))
        while ts < end:
            level, tpl = rng.choice(templates)
            if level == "WARN" and rng.random() < 0.7:
                level, tpl = templates[0]  # keep warnings rare
            lines.append({"ts": ts, "service": svc, "level": level,
                          "message": fill(tpl, rng, svc)})
            ts += timedelta(seconds=rng.randint(90, 300))

    for eff in sc.logs:
        t0 = at(sc.day, eff.at)
        t1 = min(at(sc.day, eff.end), end) if eff.end else end
        if eff.once:
            times = [t0 + timedelta(seconds=rng.randint(0, 20))]
        else:
            times, ts = [], t0
            while ts < t1:
                if eff.rate >= 1 or rng.random() < eff.rate:
                    count = max(1, round(eff.rate * rng.uniform(0.7, 1.3)))
                    times += [ts + timedelta(seconds=rng.randint(0, 59)) for _ in range(count)]
                ts += timedelta(minutes=1)
        for ts in times:
            line = {"ts": ts, "service": eff.service, "level": eff.level,
                    "message": fill(eff.template, rng, eff.service)}
            lines.append(line)
            if eff.key:
                keyed.append((line, eff.key))

    lines = [ln for ln in lines
             if not (ln["service"] in blackout and ln["ts"] >= blackout[ln["service"]])]
    lines = [ln for ln in lines if start <= ln["ts"] < end]
    lines.sort(key=lambda ln: (ln["ts"], ln["service"]))
    for n, ln in enumerate(lines, 1):
        ln["id"] = f"log-{n:05d}"
    key_ids: dict[str, list[str]] = {}
    for line, key in keyed:
        if "id" in line:
            key_ids.setdefault(key, []).append(line["id"])
    out = [{"id": ln["id"], "ts": iso(ln["ts"]), "service": ln["service"],
            "level": ln["level"], "message": ln["message"]} for ln in lines]
    return out, key_ids


def build_changes(sc: Scenario, start: datetime, rng: random.Random):
    involved = set(sc.symptom_services)
    if sc.truth.service:
        involved.add(sc.truth.service)
    internal = [s for s, v in SERVICES.items() if v[0] in ("api", "db", "cache", "queue")]
    changes: list[dict] = []
    for _ in range(18):  # routine changes over the past week, before the data window
        ts = start - timedelta(minutes=rng.randint(60, 7 * 24 * 60))
        kind, tpl = rng.choice(ROUTINE_CHANGES)
        svc = rng.choice(internal)
        changes.append({"ts": ts, "service": svc, "kind": kind,
                        "summary": f"{svc} " + tpl.replace("{v}", f"{rng.randint(1, 9)}."
                                                           f"{rng.randint(0, 20)}."
                                                           f"{rng.randint(0, 9)}"),
                        "author": rng.choice(["ci (dev)", "ci (ananya)", "platform-bot",
                                              "ci (meera)"]),
                        "details": {}})
    for _ in range(2):  # harmless changes inside the window, on uninvolved services
        svc = rng.choice([s for s in internal if s not in involved])
        ts = start + timedelta(minutes=rng.randint(5, 50))
        changes.append({"ts": ts, "service": svc, "kind": "deploy",
                        "summary": f"{svc} v{rng.randint(1, 6)}.{rng.randint(0, 30)}.0: "
                                   "routine release", "author": "ci (dev)", "details": {}})
    keyed: dict[str, dict] = {}
    for ch in sc.changes:
        entry = {"ts": at(sc.day, ch.at), "service": ch.service, "kind": ch.kind,
                 "summary": ch.summary, "author": ch.author, "details": ch.details}
        changes.append(entry)
        if ch.key:
            keyed[ch.key] = entry
    changes.sort(key=lambda c: c["ts"])
    ids = rng.sample(range(1000, 9999), len(changes))
    for c, n in zip(changes, sorted(ids), strict=True):
        c["id"] = f"chg-{n}"
    out = [{"id": c["id"], "ts": iso(c["ts"]), "service": c["service"], "kind": c["kind"],
            "summary": c["summary"], "author": c["author"], "details": c["details"]}
           for c in changes]
    return out, {k: v["id"] for k, v in keyed.items()}


def build_topology() -> dict:
    return {
        "services": [
            {"name": s, "kind": k, "owner": o, "external": k == "external"}
            for s, (k, o, _, _) in SERVICES.items()
        ],
        "edges": [{"id": f"dep:{a}->{b}", "from": a, "to": b, "kind": kind}
                  for a, b, kind in EDGES],
        "notes": PLATFORM_NOTES,
    }


def resolve_keys(refs: list[str], log_keys: dict, change_keys: dict) -> list[list[str]]:
    """Ground-truth key evidence as groups: citing any ID of a group covers it."""
    groups = []
    for ref in refs:
        kind, _, name = ref.partition(":")
        if kind == "log":
            groups.append(log_keys[name])
        elif kind == "change":
            groups.append([change_keys[name]])
        else:
            groups.append([ref])
    return groups


def generate(sc: Scenario) -> None:
    rng = random.Random(f"orange-{sc.id}")
    start = at(sc.day, DATA_START)
    end = at(sc.day, sc.reported_at) + timedelta(minutes=AFTER_REPORT_MIN)
    minutes = int((end - start).total_seconds() // 60)

    logs, log_keys = build_logs(sc, start, end, rng)
    changes, change_keys = build_changes(sc, start, rng)
    out = WORLD / "incidents" / sc.id
    out.mkdir(parents=True, exist_ok=True)
    incident = {
        "id": sc.id, "title": sc.title, "reported_at": iso(at(sc.day, sc.reported_at)),
        "reporter": sc.reporter, "description": sc.description,
        "symptom_services": sc.symptom_services, "customer_impact": sc.customer_impact,
    }
    (out / "incident.json").write_text(json.dumps(incident, indent=2))
    (out / "logs.jsonl").write_text("".join(json.dumps(ln) + "\n" for ln in logs))
    (out / "metrics.json").write_text(json.dumps(build_metrics(sc, start, minutes, rng)))
    (out / "changes.json").write_text(json.dumps(changes, indent=1))
    (out / "topology.json").write_text(json.dumps(build_topology(), indent=1))
    (out / "faults.json").write_text(json.dumps(
        [{"tool": f.tool, "mode": f.mode, "times": f.times, "service": f.service}
         for f in sc.faults], indent=1))

    t = sc.truth
    TRUTH.mkdir(parents=True, exist_ok=True)
    accepted = [[t.service, t.category], *map(list, t.alternatives)] if t.service else []
    (TRUTH / f"{sc.id}.json").write_text(json.dumps({
        "id": sc.id, "verdict": t.verdict, "root_cause_service": t.service,
        "category": t.category, "accepted": accepted,
        "key_evidence": resolve_keys(t.key_evidence, log_keys, change_keys),
        "traps": t.traps, "explanation": t.explanation,
    }, indent=1))
    print(f"{sc.id}: {len(logs)} log lines, {len(changes)} changes, {minutes} min of metrics")


def main() -> None:
    WORLD.mkdir(parents=True, exist_ok=True)
    (WORLD / "history.json").write_text(json.dumps(HISTORY, indent=1))
    for sc in SCENARIOS:
        generate(sc)


if __name__ == "__main__":
    main()
