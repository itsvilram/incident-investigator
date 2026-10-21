"""The four agents the scheduler runs as tasks: Observability, Dependency, Reasoning
and Critic. Each reads the shared state, runs, and writes a typed result back."""

from investigator.agents import prompts
from investigator.agents.base import AgentRuntime, catalog_block, incident_block, run_agent
from investigator.agents.checks import blocking_flags, check_hypotheses
from investigator.harness.state import InvestigationState, Task
from investigator.models import AgentFindings, Critique, EvidenceRequest, HypothesisSet

MAX_ROUNDS = 3

EVIDENCE_AGENTS = {
    "observability": (prompts.OBSERVABILITY, ("query_logs", "query_metrics")),
    "dependency": (prompts.DEPENDENCY, ("get_deployments", "get_service_dependencies")),
}


async def run_evidence_task(rt: AgentRuntime, state: InvestigationState, task: Task) -> None:
    system, tools = EVIDENCE_AGENTS[task.agent]
    known = rt.ctx.evidence.digest(limit=40) if len(rt.ctx.evidence) else "(nothing yet)"
    user = (
        f"{incident_block(rt.ctx.world)}\n\n{catalog_block(rt.ctx.world)}\n\n"
        f"YOUR TASK ({task.id}): {task.goal}\nFocus services: {', '.join(task.services)}\n\n"
        f"Evidence the team already has (do not fetch it again):\n{known}"
    )
    state.findings[task.id] = await run_agent(
        rt, agent=task.agent, tier="fast", system=system, user=user, output=AgentFindings,
        tools=tools, max_tool_calls=8, max_turns=4,
    )


async def run_reasoning_task(rt: AgentRuntime, state: InvestigationState, task: Task) -> None:
    critique = state.latest_critique
    review = ("(first round: no review yet)" if critique is None else
              f"verdict={critique.verdict}\nissues: {critique.issues}\n"
              f"automatic checks: {state.check_flags}")
    user = (
        f"{incident_block(rt.ctx.world)}\n\n"
        f"FINDINGS FROM THE SPECIALISTS:\n{state.findings_text()}\n\n"
        f"ALL EVIDENCE RETRIEVED SO FAR:\n{rt.ctx.evidence.digest()}\n\n"
        f"EVIDENCE GAPS:\n{state.gaps_text()}\n\n"
        f"YOUR PREVIOUS HYPOTHESES:\n{state.hypotheses_text()}\n\n"
        f"CRITIC'S REVIEW OF THEM:\n{review}"
    )
    hset = await run_agent(rt, agent="reasoning", tier="strong", system=prompts.REASONING,
                           user=user, output=HypothesisSet, tools=("search_past_incidents",),
                           max_tool_calls=2, max_turns=2)
    state.hypotheses = _ranked(hset)


async def run_critic_task(rt: AgentRuntime, state: InvestigationState, task: Task) -> None:
    state.check_flags = check_hypotheses(state.hypotheses, rt.ctx)
    last_round = state.round >= MAX_ROUNDS
    user = (
        f"{incident_block(rt.ctx.world)}\n\n"
        f"HYPOTHESES:\n{state.hypotheses_text()}\n\n"
        f"AUTOMATIC CHECKS:\n" + "\n".join(state.check_flags) + "\n\n"
        f"FINDINGS:\n{state.findings_text()}\n\n"
        f"ALL EVIDENCE RETRIEVED:\n{rt.ctx.evidence.digest()}\n\n"
        f"EVIDENCE GAPS:\n{state.gaps_text()}\n\n"
        f"This is round {state.round} of at most {MAX_ROUNDS}."
        + (" It is the LAST round: choose accept or inconclusive." if last_round else "")
    )
    critique = await run_agent(rt, agent="critic", tier="strong", system=prompts.CRITIC,
                               user=user, output=Critique)
    critique = _apply_guardrails(rt, state, critique, last_round)
    state.critiques[state.round] = critique
    if state.hypotheses:
        adjust = {a.hypothesis_id: a.confidence for a in critique.adjustments}
        hyps = [h.model_copy(update={"confidence": adjust.get(h.id, h.confidence)})
                for h in state.hypotheses.hypotheses]
        state.hypotheses = _ranked(state.hypotheses.model_copy(update={"hypotheses": hyps}))


def _apply_guardrails(rt: AgentRuntime, state: InvestigationState, critique: Critique,
                      last_round: bool) -> Critique:
    """The code half of the Critic has the last word.

    A small model will sometimes accept a hypothesis that failed an automatic check
    (its trigger came after the onset, or nobody looked at the suspect directly). If a
    round remains, acceptance is vetoed and the missing check becomes a request.
    """
    blocking = blocking_flags(state.check_flags, state.hypotheses)
    if critique.verdict == "accept" and blocking and not last_round and state.hypotheses:
        top = state.hypotheses.hypotheses[0]
        request = EvidenceRequest(
            agent="observability", services=[top.root_cause_service],
            goal=f"Check {top.root_cause_service}'s own metrics and WARN/ERROR logs: is it "
                 "unhealthy, and since when?",
            reason="automatic check blocked acceptance",
        )
        rt.ctx.tracer.event("critic_veto", flags=blocking)
        critique = critique.model_copy(update={
            "verdict": "investigate_more",
            "issues": [*critique.issues, *blocking],
            "requests": [*critique.requests, request][:3],
        })
    if last_round and critique.verdict == "investigate_more":
        critique = critique.model_copy(update={"verdict": "inconclusive"})
    return critique


def _ranked(hset: HypothesisSet) -> HypothesisSet:
    return hset.model_copy(update={"hypotheses": sorted(hset.hypotheses,
                                                        key=lambda h: -h.confidence)})


async def dispatch(rt: AgentRuntime, state: InvestigationState, task: Task) -> None:
    if task.agent in EVIDENCE_AGENTS:
        await run_evidence_task(rt, state, task)
    elif task.agent == "reasoning":
        await run_reasoning_task(rt, state, task)
    elif task.agent == "critic":
        await run_critic_task(rt, state, task)
    else:
        raise ValueError(f"No agent called {task.agent!r}")
