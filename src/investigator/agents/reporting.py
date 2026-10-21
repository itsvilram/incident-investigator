"""Reporting agent: writes the final report. If it fails, code writes it instead.

`finalize` applies the same verdict rule to every report (multi-agent and baseline):
no hypotheses, or a top confidence below 0.4, means inconclusive.
"""

from investigator.agents import prompts
from investigator.agents.base import AgentFailed, AgentRuntime, incident_block, run_agent
from investigator.harness.context import BudgetExceeded
from investigator.harness.state import InvestigationState
from investigator.llm.client import LLMError
from investigator.models import Action, EvidenceRef, FinalReport, RankedHypothesis, Statement

MIN_CONFIDENCE = 0.4


async def write_report(rt: AgentRuntime, state: InvestigationState) -> FinalReport:
    critique = state.latest_critique
    user = (
        f"{incident_block(rt.ctx.world)}\n\n"
        f"FINAL HYPOTHESES:\n{state.hypotheses_text()}\n\n"
        f"CRITIC'S LAST REVIEW: verdict={critique.verdict if critique else 'none'}; "
        f"issues: {critique.issues if critique else []}\n"
        f"AUTOMATIC CHECKS: {state.check_flags}\n\n"
        f"FINDINGS:\n{state.findings_text()}\n\n"
        f"EVIDENCE:\n{rt.ctx.evidence.digest()}\n\n"
        f"EVIDENCE GAPS:\n{state.gaps_text()}\n\n"
        f"Investigation ended because: {state.stop_reason}"
    )
    try:
        report = await run_agent(rt, agent="reporting", tier="fast", system=prompts.REPORTING,
                                 user=user, output=FinalReport, use_reserve=True)
    except (AgentFailed, LLMError, BudgetExceeded) as error:
        rt.ctx.tracer.event("reporting_fallback", error=str(error)[:200])
        rt.ctx.gaps.append(f"reporting agent failed ({error}); report assembled by code")
        report = fallback_report(state)
    if critique and critique.verdict == "inconclusive":
        report = report.model_copy(update={"verdict": "inconclusive"})
    return finalize(report)


def finalize(report: FinalReport) -> FinalReport:
    ranked = sorted(report.ranked_hypotheses, key=lambda h: (h.rank, -h.confidence))
    ranked = [h.model_copy(update={"rank": i}) for i, h in enumerate(ranked, 1)]
    verdict = report.verdict
    if not ranked or ranked[0].confidence < MIN_CONFIDENCE:
        verdict = "inconclusive"
    return report.model_copy(update={"ranked_hypotheses": ranked, "verdict": verdict})


def fallback_report(state: InvestigationState) -> FinalReport:
    """A plain report built from the shared state, used when the LLM cannot write one."""
    hyps = state.hypotheses.hypotheses if state.hypotheses else []
    facts = [Statement(text=f.statement, evidence_ids=f.evidence_ids)
             for findings in state.findings.values() for f in findings.findings
             if f.kind == "fact"][:12]
    top = hyps[0] if hyps else None
    return FinalReport(
        verdict="root_cause_identified" if top and top.confidence >= 0.6 else "inconclusive",
        summary=(f"Most likely: {top.title} ({top.confidence:.0%})." if top
                 else "No hypothesis could be formed from the available evidence."),
        ranked_hypotheses=[
            RankedHypothesis(rank=i, title=h.title, root_cause_service=h.root_cause_service,
                             category=h.category, confidence=h.confidence,
                             supporting=h.supporting, contradicting=h.contradicting)
            for i, h in enumerate(hyps, 1)
        ],
        facts=facts,
        assumptions=[a for h in hyps[:1] for a in h.assumptions],
        evidence_gaps=list(dict.fromkeys(state.ctx.gaps)),
        timeline=[],
        recommended_actions=[Action(
            action=(f"Investigate and mitigate {top.root_cause_service}: {top.title}" if top
                    else "Collect the missing telemetry listed under evidence gaps"),
            priority="immediate", rationale="Top-ranked hypothesis" if top else "No evidence",
            evidence_ids=[r.evidence_id for r in (top.supporting if top else [])][:5],
        )],
    )


def empty_report(reason: str) -> FinalReport:
    return FinalReport(verdict="inconclusive", summary=f"Investigation failed: {reason}",
                       ranked_hypotheses=[], facts=[], assumptions=[], evidence_gaps=[reason],
                       timeline=[], recommended_actions=[])


def cited_ids(report: FinalReport) -> list[str]:
    """Every evidence ID the report cites, in order of first appearance."""
    ids: list[str] = []
    for h in report.ranked_hypotheses:
        ids += [r.evidence_id for r in h.supporting + h.contradicting]
    for s in report.facts:
        ids += s.evidence_ids
    ids += [t.evidence_id for t in report.timeline if t.evidence_id]
    for a in report.recommended_actions:
        ids += a.evidence_ids
    return list(dict.fromkeys(ids))


def render_markdown(report: FinalReport, *, title: str, meta: dict[str, object]) -> str:
    def refs(items: list[EvidenceRef]) -> str:
        return "<br>".join(f"`{r.evidence_id}` {r.note}" for r in items) or "-"

    lines = [f"# {title}", "",
             f"**Verdict:** {report.verdict.replace('_', ' ')}", "", report.summary, "",
             " · ".join(f"{k}: {v}" for k, v in meta.items()), "",
             "## Ranked hypotheses", "",
             "| # | Hypothesis | Service | Category | Confidence | Supporting | Contradicting |",
             "|---|---|---|---|---|---|---|"]
    for h in report.ranked_hypotheses:
        lines.append(f"| {h.rank} | {h.title} | {h.root_cause_service} | {h.category} | "
                     f"{h.confidence:.2f} | {refs(h.supporting)} | {refs(h.contradicting)} |")
    lines += ["", "## Facts (evidence-backed)", ""]
    lines += [f"- {s.text} ({', '.join(f'`{i}`' for i in s.evidence_ids)})"
              for s in report.facts] or ["- none"]
    lines += ["", "## Assumptions (not proven)", ""]
    lines += [f"- {a}" for a in report.assumptions] or ["- none"]
    lines += ["", "## Evidence gaps", ""]
    lines += [f"- {g}" for g in report.evidence_gaps] or ["- none"]
    lines += ["", "## Timeline", ""]
    lines += [f"- {t.ts:%H:%M} {t.event}" + (f" (`{t.evidence_id}`)" if t.evidence_id else "")
              for t in report.timeline] or ["- none"]
    lines += ["", "## Recommended actions", ""]
    lines += [f"- **{a.priority}**: {a.action}. {a.rationale}"
              + (f" ({', '.join(f'`{i}`' for i in a.evidence_ids)})" if a.evidence_ids else "")
              for a in report.recommended_actions] or ["- none"]
    return "\n".join(lines) + "\n"
