"""Orchestrator: plans each round of evidence gathering, and when to stop.

If the LLM call fails, it falls back to a plan made by code (check the symptomatic
services; turn the Critic's requests into tasks), so the investigation goes on.
"""

from investigator.agents import prompts
from investigator.agents.base import (
    AgentFailed,
    AgentRuntime,
    catalog_block,
    incident_block,
    run_agent,
)
from investigator.harness.state import InvestigationState
from investigator.llm.client import LLMError
from investigator.models import InvestigationPlan, PlannedTask


async def plan_first_round(rt: AgentRuntime, state: InvestigationState) -> InvestigationPlan:
    user = (f"{incident_block(rt.ctx.world)}\n\n{catalog_block(rt.ctx.world)}\n\n"
            "Plan the first round of evidence gathering.")
    try:
        plan = await run_agent(rt, agent="orchestrator", tier="fast",
                               system=prompts.ORCHESTRATOR, user=user,
                               output=InvestigationPlan)
        plan = _clean(plan, state)
        if not plan.tasks:
            raise AgentFailed("empty first plan")
    except (AgentFailed, LLMError) as error:
        rt.ctx.tracer.event("orchestrator_fallback", error=str(error)[:200])
        rt.ctx.gaps.append(f"orchestrator failed ({error}); used the default plan")
        plan = _default_plan(state)
    state.plans.append(plan)
    return plan


async def plan_next_round(rt: AgentRuntime, state: InvestigationState) -> InvestigationPlan:
    critique = state.latest_critique
    budget = rt.ctx.budget
    user = (
        f"{incident_block(rt.ctx.world)}\n\n{catalog_block(rt.ctx.world)}\n\n"
        f"TASKS SO FAR:\n{state.tasks_text()}\n\n"
        f"CURRENT HYPOTHESES:\n{state.hypotheses_text()}\n\n"
        f"CRITIC (round {state.round}): verdict={critique.verdict if critique else 'none'}\n"
        f"issues: {critique.issues if critique else []}\n"
        f"requests: {[r.model_dump() for r in critique.requests] if critique else []}\n\n"
        f"EVIDENCE GAPS:\n{state.gaps_text()}\n\n"
        f"Budget used: {budget.tool_calls}/{budget.max_tool_calls} tool calls, "
        f"{budget.llm_calls}/{budget.max_llm_calls} LLM calls.\n"
        "Plan the next round, or set stop=true."
    )
    try:
        plan = _clean(await run_agent(rt, agent="orchestrator", tier="fast",
                                      system=prompts.ORCHESTRATOR, user=user,
                                      output=InvestigationPlan), state)
    except (AgentFailed, LLMError) as error:
        rt.ctx.tracer.event("orchestrator_fallback", error=str(error)[:200])
        plan = InvestigationPlan(
            rationale="Fallback: the Critic's requests as tasks.",
            tasks=[PlannedTask(agent=r.agent, goal=r.goal, services=r.services)
                   for r in (critique.requests if critique else [])][:3],
            stop=not (critique and critique.requests),
        )
    state.plans.append(plan)
    return plan


def _clean(plan: InvestigationPlan, state: InvestigationState) -> InvestigationPlan:
    """Keep at most 3 tasks and only real service names (models sometimes invent some)."""
    known = set(state.ctx.world.service_names)
    tasks = []
    for t in plan.tasks[:3]:
        services = [s for s in t.services if s in known]
        tasks.append(t.model_copy(update={"services": services or
                                          state.incident.symptom_services}))
    return plan.model_copy(update={"tasks": tasks})


def _default_plan(state: InvestigationState) -> InvestigationPlan:
    services = state.incident.symptom_services
    return InvestigationPlan(
        rationale="Default plan: look at the symptomatic services and recent changes.",
        tasks=[
            PlannedTask(agent="observability", services=services,
                        goal="When did errors, latency or saturation start on these services,"
                             " and what do their WARN/ERROR logs say?"),
            PlannedTask(agent="dependency", services=services,
                        goal="What changed in the hours before the report, across all "
                             "services, and what do these services depend on?"),
        ],
        stop=False,
    )
