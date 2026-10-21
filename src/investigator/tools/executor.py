"""Run tools the way a flaky production backend would answer them.

Every tool call goes through ToolExecutor.call, which:
  1. validates the arguments against the tool's input model,
  2. charges the run's budget (each attempt counts as a tool call),
  3. injects failures: scripted ones from the incident's faults.json, plus a small
     seeded random rate, as timeouts, 503 errors or partial results,
  4. retries transient failures with backoff, a bounded number of times,
  5. records successful items in the shared evidence store, failures as evidence gaps,
  6. traces every attempt.

It never raises for tool problems: the agent gets a structured error result and
decides what to do. Only BudgetExceeded propagates, because that ends the run.
"""

import asyncio
import hashlib
import json
from collections import Counter
from typing import Any

from pydantic import ValidationError

from investigator.harness.context import RunContext
from investigator.tools.catalog import TOOLS, ToolInputError


class ToolUnavailable(Exception):
    """The backend answered with an error (simulated 503)."""


class FaultInjector:
    def __init__(self, ctx: RunContext) -> None:
        self._rules = ctx.world.faults
        self._used: Counter[int] = Counter()
        self._rate = ctx.random_fault_rate
        self._seed = ctx.seed

    def decide(self, tool: str, args: dict[str, Any], attempt: int) -> str | None:
        """The failure mode for this attempt, or None for a normal answer."""
        for i, rule in enumerate(self._rules):
            if rule.tool != tool or (rule.service and args.get("service") != rule.service):
                continue
            if self._used[i] < rule.times:
                self._used[i] += 1
                return rule.mode
        # Random faults depend on the call itself, not on call order, so parallel agents
        # see the same failures on every run with the same seed.
        key = f"{self._seed}|{tool}|{json.dumps(args, sort_keys=True, default=str)}|{attempt}"
        roll = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if roll < self._rate:
            return ("timeout", "error", "partial")[int(roll * 1000) % 3]
        return None


class ToolExecutor:
    def __init__(
        self,
        ctx: RunContext,
        *,
        max_attempts: int = 3,
        timeout_s: float = 0.3,
        backoff_s: float = 0.05,
    ) -> None:
        self.ctx = ctx
        self.faults = FaultInjector(ctx)
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.backoff_s = backoff_s

    async def call(self, agent: str, name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
        spec = TOOLS.get(name)
        if spec is None:
            return {"status": "error", "error": f"Unknown tool {name!r}.", "retryable": False}
        try:
            args = spec.input.model_validate(raw_args)
        except ValidationError as error:
            return {"status": "error", "retryable": False,
                    "error": f"Invalid arguments: {_short(error)}"}
        plain_args = args.model_dump(mode="json", exclude_none=True)

        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            self.ctx.budget.charge_tool_call()  # BudgetExceeded ends the run on purpose
            mode = self.faults.decide(name, plain_args, attempt)
            with self.ctx.tracer.span("tool", name, agent=agent, attempt=attempt,
                                      args=plain_args, fault=mode) as span:
                try:
                    result, evidence = await asyncio.wait_for(
                        self._run(spec, args, mode), timeout=self.timeout_s
                    )
                except TimeoutError:
                    last_error = f"timed out after {self.timeout_s}s"
                    span["status"] = "timeout"
                except ToolUnavailable as error:
                    last_error = str(error)
                    span["status"] = "unavailable"
                except ToolInputError as error:
                    span["status"] = "bad_input"
                    return {"status": "error", "error": str(error), "retryable": False}
                else:
                    for item in evidence:
                        self.ctx.evidence.add(item.model_copy(update={"retrieved_by": agent}))
                    status = "partial" if mode == "partial" else "ok"
                    span["status"] = status
                    span["evidence"] = len(evidence)
                    if status == "partial":
                        self.ctx.gaps.append(
                            f"{name}({_brief(plain_args)}) returned partial data")
                    return {"status": status, "attempts": attempt, **result}
            if attempt < self.max_attempts:
                await asyncio.sleep(self.backoff_s * 2 ** (attempt - 1))

        gap = f"{name}({_brief(plain_args)}) failed: {last_error} after {self.max_attempts} tries"
        self.ctx.gaps.append(gap)
        return {"status": "error", "retryable": True, "attempts": self.max_attempts,
                "error": f"{last_error} (after {self.max_attempts} attempts). The backend may "
                         "recover: retry later, or use another source."}

    async def _run(self, spec, args, mode: str | None):
        if mode == "timeout":
            await asyncio.sleep(self.timeout_s * 2)  # wait_for cancels this
        if mode == "error":
            raise ToolUnavailable(f"{spec.name} backend returned 503 Service Unavailable")
        await asyncio.sleep(0)  # a real backend would await I/O here
        return spec.run(self.ctx.world, args, mode == "partial")


def _brief(args: dict[str, Any]) -> str:
    keep = {k: v for k, v in args.items() if k in ("service", "metrics", "contains", "query")}
    return ", ".join(f"{k}={v}" for k, v in keep.items())


def _short(error: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:4])
