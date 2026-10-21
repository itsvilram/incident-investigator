"""The multi-agent investigation: rounds of plan -> gather (parallel) -> reason -> critique,
until the Critic is satisfied or a limit is reached, then the report.

Stop conditions, checked after every round:
  - the Critic accepts, or says the evidence cannot settle it (inconclusive);
  - MAX_ROUNDS rounds are done;
  - a round added no new evidence (more rounds would repeat themselves);
  - the Orchestrator decides nothing more is worth gathering;
  - the budget (tool calls, LLM calls, tokens, time) runs out at any point.
"""

import time

from investigator.agents import orchestrator
from investigator.agents.base import AgentRuntime
from investigator.agents.reporting import write_report
from investigator.agents.specialists import MAX_ROUNDS, dispatch
from investigator.harness.context import Budget, BudgetExceeded, RunContext
from investigator.harness.scheduler import run_tasks
from investigator.harness.state import InvestigationState
from investigator.llm.router import Router
from investigator.runs import RunResult
from investigator.tools.executor import ToolExecutor
from investigator.world import World


async def investigate(
    world: World,
    router: Router,
    *,
    budget: Budget | None = None,
    seed: int = 7,
    fault_rate: float = 0.05,
    max_parallel: int = 3,
) -> tuple[RunResult, InvestigationState]:
    ctx = RunContext(world=world, budget=budget or Budget(), seed=seed,
                     random_fault_rate=fault_rate)
    rt = AgentRuntime(ctx=ctx, router=router, tools=ToolExecutor(ctx))
    state = InvestigationState(ctx=ctx)
    started = time.monotonic()

    with ctx.tracer.span("run", "multi_agent", incident=world.incident.id):
        try:
            plan = await orchestrator.plan_first_round(rt, state)
            while True:
                state.round += 1
                evidence_before = len(ctx.evidence)
                tasks = state.schedule_round(plan.tasks)
                await run_tasks(tasks, lambda t: dispatch(rt, state, t), ctx=ctx,
                                max_parallel=max_parallel)
                critique = state.critiques.get(state.round)
                new_evidence = len(ctx.evidence) - evidence_before
                ctx.tracer.event("round_done", round=state.round, new_evidence=new_evidence,
                                 verdict=critique.verdict if critique else None)
                if critique is None:
                    state.stop_reason = ("no critique this round (reasoning or critic failed);"
                                         " reporting the best available hypotheses")
                    break
                if critique.verdict == "accept":
                    state.stop_reason = "critic accepted the top hypothesis"
                    break
                if critique.verdict == "inconclusive":
                    state.stop_reason = "critic: evidence cannot settle it (inconclusive)"
                    break
                if state.round >= MAX_ROUNDS:
                    state.stop_reason = f"reached the round limit ({MAX_ROUNDS})"
                    break
                if state.round > 1 and new_evidence == 0:
                    state.stop_reason = "the last round found no new evidence"
                    break
                plan = await orchestrator.plan_next_round(rt, state)
                if plan.stop or not plan.tasks:
                    state.stop_reason = "orchestrator: nothing more worth gathering"
                    break
        except BudgetExceeded as error:
            state.stop_reason = f"budget exhausted: {error}"
            ctx.tracer.event("budget_exhausted", reason=str(error))

        report = await write_report(rt, state)

    result = RunResult.from_context(
        "multi_agent", ctx, report, stop_reason=state.stop_reason or "unknown",
        rounds=state.round, latency_s=time.monotonic() - started, models=router.describe(),
    )
    return result, state


def state_snapshot(state: InvestigationState) -> dict:
    """The shared state at the end, for the run folder (debugging and the write-up)."""
    return {
        "stop_reason": state.stop_reason,
        "rounds": state.round,
        "plans": [p.model_dump(mode="json") for p in state.plans],
        "tasks": [{k: v for k, v in vars(t).items()} for t in state.tasks],
        "findings": {k: v.model_dump(mode="json") for k, v in state.findings.items()},
        "hypotheses": state.hypotheses.model_dump(mode="json") if state.hypotheses else None,
        "critiques": {r: c.model_dump(mode="json") for r, c in state.critiques.items()},
        "check_flags": state.check_flags,
        "gaps": list(dict.fromkeys(state.ctx.gaps)),
    }
