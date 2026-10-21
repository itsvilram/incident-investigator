"""Automatic checks on hypotheses: plain code, no LLM.

The Critic gets these as facts it cannot argue away. They catch the classic failure
modes of an LLM investigator: citing evidence it never saw, blaming a change that
happened after the symptoms began, and trusting a service it never looked at.
"""

from datetime import timedelta

from investigator.harness.context import RunContext
from investigator.models import HypothesisSet

ONSET_TOLERANCE = timedelta(minutes=2)


def check_hypotheses(hset: HypothesisSet | None, ctx: RunContext) -> list[str]:
    if hset is None or not hset.hypotheses:
        return ["FAIL: no hypotheses were produced."]
    store = ctx.evidence
    flags: list[str] = []
    ranked = sorted(hset.hypotheses, key=lambda h: -h.confidence)

    for h in ranked:
        cited = [r.evidence_id for r in h.supporting + h.contradicting]
        if h.trigger_evidence_id:
            cited.append(h.trigger_evidence_id)
        unknown = [i for i in dict.fromkeys(cited) if not store.has(i)]
        if unknown:
            flags.append(f"FAIL: {h.id} cites evidence never retrieved in this "
                         f"investigation: {unknown[:6]}")
        if not h.supporting:
            flags.append(f"FAIL: {h.id} has no supporting evidence.")
        if h.root_cause_service not in ctx.world.service_names:
            flags.append(f"FAIL: {h.id} names unknown service {h.root_cause_service!r}.")
        trigger = store.items.get(h.trigger_evidence_id or "")
        if trigger and trigger.ts and hset.onset and trigger.ts > hset.onset + ONSET_TOLERANCE:
            flags.append(
                f"FAIL: {h.id}'s trigger {trigger.id} is at {trigger.ts:%H:%M}, AFTER the "
                f"symptom onset {hset.onset:%H:%M}: it cannot have caused the incident."
            )

    if hset.onset is None:
        flags.append("WARN: the symptom onset was not established.")
    top = ranked[0]
    observed = {e.service for e in store.items.values() if e.source in ("logs", "metrics")}
    if top.root_cause_service not in observed:
        flags.append(f"WARN: no logs or metrics of {top.root_cause_service} (top hypothesis "
                     f"{top.id}) were retrieved: its own health is unverified.")
    if len(ranked) > 1 and ranked[0].confidence - ranked[1].confidence < 0.15:
        flags.append(f"WARN: {ranked[0].id} and {ranked[1].id} are within 0.15 confidence: "
                     "the ranking is not settled.")
    for gap in dict.fromkeys(ctx.gaps):
        if top.root_cause_service in gap:
            flags.append(f"WARN: evidence gap on the top suspect: {gap}")

    earliest = sorted((e for e in store.items.values() if e.source == "metrics" and e.ts),
                      key=lambda e: e.ts)[:6]
    if earliest:
        flags.append("INFO: earliest metric anomalies retrieved: " + "; ".join(
            f"{e.service} {e.id.rsplit(':', 1)[-1]} from {e.ts:%H:%M}" for e in earliest))
    if not any(f.startswith(("FAIL", "WARN")) for f in flags):
        flags.insert(0, "PASS: citations valid, trigger timing consistent, top suspect "
                        "observed directly.")
    return flags


def blocking_flags(flags: list[str], hset: HypothesisSet | None) -> list[str]:
    """Check results that forbid accepting the top hypothesis yet."""
    if hset is None or not hset.hypotheses:
        return flags
    top = max(hset.hypotheses, key=lambda h: h.confidence)
    return [f for f in flags
            if (f.startswith("FAIL") and (f"{top.id} " in f or f"{top.id}'s" in f))
            or "health is unverified" in f]
