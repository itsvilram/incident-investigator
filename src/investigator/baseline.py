"""The single-agent baseline: one agent, the same five tools, the same budget, the same
report format and verdict rule. No specialists, no critic, no feedback loop."""

import time

from investigator.agents import prompts
from investigator.agents.base import (
    AgentFailed,
    AgentRuntime,
    catalog_block,
    incident_block,
    run_agent,
)
from investigator.agents.reporting import empty_report, finalize
from investigator.harness.context import Budget, BudgetExceeded, RunContext
from investigator.llm.client import LLMError
from investigator.llm.router import Router
from investigator.models import FinalReport
from investigator.runs import RunResult
from investigator.tools.catalog import TOOLS
from investigator.tools.executor import ToolExecutor
from investigator.world import World


async def investigate(
    world: World,
    router: Router,
    *,
    budget: Budget | None = None,
    seed: int = 7,
    fault_rate: float = 0.05,
) -> tuple[RunResult, RunContext]:
    ctx = RunContext(world=world, budget=budget or Budget(), seed=seed,
                     random_fault_rate=fault_rate)
    rt = AgentRuntime(ctx=ctx, router=router, tools=ToolExecutor(ctx))
    started = time.monotonic()
    stop_reason = "agent finished"

    with ctx.tracer.span("run", "baseline", incident=world.incident.id):
        try:
            report = await run_agent(
                rt, agent="baseline", tier="strong", system=prompts.BASELINE,
                user=f"{incident_block(world)}\n\n{catalog_block(world)}\n\nInvestigate.",
                output=FinalReport, tools=tuple(TOOLS),
                max_tool_calls=ctx.budget.max_tool_calls, max_turns=15,
                finish_on_budget=True,
            )
            if ctx.budget.exhausted_reason:
                stop_reason = f"budget exhausted: {ctx.budget.exhausted_reason}"
        except (AgentFailed, LLMError, BudgetExceeded) as error:
            stop_reason = f"agent failed: {error}"
            ctx.gaps.append(stop_reason)
            report = empty_report(str(error))
        report = finalize(report)

    result = RunResult.from_context("baseline", ctx, report, stop_reason=stop_reason,
                                    rounds=1, latency_s=time.monotonic() - started,
                                    models=router.describe())
    return result, ctx
