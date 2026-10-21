"""The one loop every agent runs: optional tool use, then a validated structured answer.

  1. Tool phase (if the agent has tools): the model calls tools, several per turn if it
     likes (they run in parallel); results go back as tool messages. Bounded by
     `max_tool_calls` and `max_turns`.
  2. Answer phase: the model must answer with JSON matching the output model's schema.
     Invalid JSON gets one repair attempt with the validation error shown.
"""

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from investigator.harness.context import BudgetExceeded, RunContext
from investigator.llm.router import Router
from investigator.llm.schema import llm_schema, tool_definition
from investigator.tools.catalog import TOOLS
from investigator.tools.executor import ToolExecutor
from investigator.world import World

FINAL_INSTRUCTION = (
    "Stop calling tools. Now give your answer as JSON matching the required schema. "
    "Cite only evidence IDs that appeared in tool results or in the material above."
)


class AgentFailed(Exception):
    """The agent could not produce a valid answer."""


@dataclass
class AgentRuntime:
    ctx: RunContext
    router: Router
    tools: ToolExecutor


async def run_agent[T: BaseModel](
    rt: AgentRuntime,
    *,
    agent: str,
    tier: str,
    system: str,
    user: str,
    output: type[T],
    tools: Sequence[str] = (),
    max_tool_calls: int = 8,
    max_turns: int = 5,
    finish_on_budget: bool = False,
    use_reserve: bool = False,
) -> T:
    """finish_on_budget: when the budget runs out during tool use, still write the answer
    (from the reserve) instead of failing. The baseline uses this; it has no reporter."""
    messages: list[dict] = [{"role": "system", "content": system},
                            {"role": "user", "content": user}]
    with rt.ctx.tracer.span("agent", agent) as span:
        if tools:
            definitions = [tool_definition(TOOLS[name]) for name in tools]
            used = 0
            try:
                for _ in range(max_turns):
                    response = await rt.router.chat(rt.ctx, agent=agent, tier=tier,
                                                    messages=messages, tools=definitions)
                    messages.append(response.message)
                    if not response.tool_calls:
                        break
                    allowed = response.tool_calls[: max(0, max_tool_calls - used)]
                    results = await asyncio.gather(
                        *(rt.tools.call(agent, c.name, c.arguments) for c in allowed))
                    used += len(allowed)
                    for call in response.tool_calls:
                        result = (results[allowed.index(call)] if call in allowed else
                                  {"status": "error",
                                   "error": "Tool-call limit for this task reached."})
                        messages.append({"role": "tool", "tool_call_id": call.id,
                                         "name": call.name,
                                         "content": json.dumps(result, default=str,
                                                               separators=(",", ":"))})
                    if used >= max_tool_calls:
                        break
            except BudgetExceeded:
                if not finish_on_budget:
                    raise
                use_reserve = True
                rt.ctx.tracer.event("budget_stop_writing_answer", agent=agent)
            span["tool_calls"] = used
            messages.append({"role": "user", "content": FINAL_INSTRUCTION})

        schema = (output.__name__, llm_schema(output, strict=True))
        for attempt in range(2):
            response = await rt.router.chat(rt.ctx, agent=agent, tier=tier, messages=messages,
                                            schema=schema, use_reserve=use_reserve)
            try:
                return output.model_validate_json(json_text(response.content))
            except ValidationError as error:
                problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                                     for e in error.errors()[:6])
                rt.ctx.tracer.event("invalid_output", agent=agent, attempt=attempt,
                                    problems=problems[:300])
                messages += [response.message,
                             {"role": "user", "content": f"That JSON is invalid: {problems}. "
                                                         "Reply with the corrected JSON only."}]
        raise AgentFailed(f"{agent} produced no valid {output.__name__}")


def json_text(content: str | None) -> str:
    """The JSON object in a reply, without code fences or chatter around it."""
    text = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start: end + 1] if start != -1 and end > start else text


def incident_block(world: World) -> str:
    inc = world.incident
    return (
        f"INCIDENT {inc.id}: {inc.title}\n"
        f"Reported at {inc.reported_at.isoformat()} by {inc.reporter}.\n"
        f"Report (claims to verify, not evidence): {inc.description}\n"
        f"Symptomatic services: {', '.join(inc.symptom_services)}\n"
        f"Customer impact: {inc.customer_impact}\n"
        f"Telemetry (logs, metrics) covers {world.data_start.isoformat()} to "
        f"{world.data_end.isoformat()}. The change log goes back 7 days."
    )


def catalog_block(world: World) -> str:
    by_kind: dict[str, list[str]] = {}
    for s in world.topology["services"]:
        by_kind.setdefault(s["kind"], []).append(s["name"])
    return "Service catalog:\n" + "\n".join(f"- {kind}: {', '.join(names)}"
                                            for kind, names in by_kind.items())
