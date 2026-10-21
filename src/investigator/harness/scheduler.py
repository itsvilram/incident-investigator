"""Run a set of tasks with dependencies: in parallel where possible, with retries.

  - a task starts once everything in `depends_on` and `requires` has finished;
  - it is skipped if something in `requires` failed (no hypotheses -> nothing to critique);
  - up to `max_parallel` tasks run at once;
  - each attempt has a time limit; a failed task is retried up to `max_attempts`, then
    marked failed and recorded as an evidence gap, and the rest carry on;
  - BudgetExceeded cancels everything still running and propagates: the run is over.
"""

import asyncio
from collections.abc import Awaitable, Callable

from investigator.harness.context import BudgetExceeded, RunContext
from investigator.harness.state import Task

_FINISHED = ("done", "failed", "skipped")


async def run_tasks(
    tasks: list[Task],
    run: Callable[[Task], Awaitable[None]],
    *,
    ctx: RunContext,
    max_parallel: int = 3,
    task_timeout_s: float = 180.0,
) -> None:
    by_id = {t.id: t for t in tasks}
    waiting = list(tasks)
    running: dict[asyncio.Task[None], Task] = {}

    def finished(task_id: str) -> bool:
        dep = by_id.get(task_id)
        return dep is None or dep.status in _FINISHED

    async def attempt(task: Task) -> None:
        with ctx.tracer.span("task", task.id, agent=task.agent, attempt=task.attempts):
            await asyncio.wait_for(run(task), timeout=task_timeout_s)

    try:
        while waiting or running:
            for task in list(waiting):
                if any(by_id[r].status in ("failed", "skipped") for r in task.requires
                       if r in by_id):
                    waiting.remove(task)
                    task.status, task.error = "skipped", "a required task failed"
                    ctx.tracer.event("task_skipped", task=task.id)
                    continue
                ready = all(finished(d) for d in task.depends_on + task.requires)
                if ready and len(running) < max_parallel:
                    waiting.remove(task)
                    task.status = "running"
                    task.attempts += 1
                    running[asyncio.create_task(attempt(task))] = task
            if not running:
                for task in waiting:  # dependencies that can never finish
                    task.status, task.error = "skipped", "unsatisfiable dependency"
                break

            done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for fut in done:
                task = running.pop(fut)
                error = fut.exception()
                if error is None:
                    task.status = "done"
                elif isinstance(error, BudgetExceeded):
                    task.status, task.error = "failed", str(error)
                    raise error
                elif task.attempts < task.max_attempts:
                    task.status = "pending"
                    waiting.append(task)
                    ctx.tracer.event("task_retry", task=task.id, error=_describe(error))
                else:
                    task.status, task.error = "failed", _describe(error)
                    ctx.gaps.append(f"{task.agent} task '{task.goal[:80]}' failed: "
                                    f"{task.error}")
    finally:
        for fut in running:
            fut.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)


def _describe(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "timed out"
    return f"{type(error).__name__}: {error}"[:200]
