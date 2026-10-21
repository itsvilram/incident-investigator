"""Scheduler, automatic checks and LLM routing: the reliability machinery."""

import asyncio
import time
from datetime import UTC, datetime

import httpx
import pytest

from investigator.agents.checks import blocking_flags, check_hypotheses
from investigator.harness.context import Budget, BudgetExceeded, RunContext
from investigator.harness.scheduler import run_tasks
from investigator.harness.state import Task
from investigator.llm.cache import ResponseCache
from investigator.llm.client import LLMError, LLMRateLimited, OpenAICompatClient
from investigator.llm.fake import ScriptedClient
from investigator.llm.router import Router
from investigator.models import EvidenceItem, EvidenceRef, Hypothesis, HypothesisSet
from investigator.world import World


def ctx(**budget) -> RunContext:
    return RunContext(world=World.load("INC-02"), budget=Budget(**budget))


# --- scheduler ---------------------------------------------------------------------

async def test_independent_tasks_run_in_parallel_and_dependents_wait():
    c = ctx()
    order: list[str] = []
    tasks = [Task("a", "observability", "", [], 1), Task("b", "dependency", "", [], 1),
             Task("c", "reasoning", "", [], 1, depends_on=["a", "b"])]

    async def run(task):
        order.append(f"start {task.id}")
        await asyncio.sleep(0.2)
        order.append(f"end {task.id}")

    started = time.monotonic()
    await run_tasks(tasks, run, ctx=c)
    assert time.monotonic() - started < 0.55  # a and b overlapped: 0.4s, not 0.6s
    assert order.index("start c") > max(order.index("end a"), order.index("end b"))
    assert all(t.status == "done" for t in tasks)


async def test_failed_task_is_retried_then_recorded_and_the_rest_continue():
    c = ctx()
    attempts = {"a": 0}
    tasks = [Task("a", "observability", "look at logs", [], 1),
             Task("c", "reasoning", "", [], 1, depends_on=["a"]),
             Task("d", "critic", "", [], 1, requires=["a"])]

    async def run(task):
        if task.id == "a":
            attempts["a"] += 1
            raise RuntimeError("agent crashed")

    await run_tasks(tasks, run, ctx=c)
    status = {t.id: t.status for t in tasks}
    assert attempts["a"] == 2  # bounded retry
    assert status == {"a": "failed", "c": "done", "d": "skipped"}
    assert any("look at logs" in gap for gap in c.gaps)


async def test_task_timeout_counts_as_a_failure():
    c = ctx()
    task = Task("slow", "observability", "", [], 1, max_attempts=1)

    async def run(task):
        await asyncio.sleep(5)

    await run_tasks([task], run, ctx=c, task_timeout_s=0.05)
    assert task.status == "failed" and task.error == "timed out"


async def test_budget_exhaustion_stops_everything():
    c = ctx()
    tasks = [Task("a", "observability", "", [], 1), Task("b", "dependency", "", [], 1)]

    async def run(task):
        if task.id == "a":
            raise BudgetExceeded("tool-call limit")
        await asyncio.sleep(5)

    with pytest.raises(BudgetExceeded):
        await run_tasks(tasks, run, ctx=c)


# --- automatic checks -------------------------------------------------------------

def hypothesis(hid: str, service: str, trigger: str | None, support: list[str],
               confidence: float) -> Hypothesis:
    return Hypothesis(id=hid, title=hid, root_cause_service=service, category="bad_deploy",
                      mechanism="", trigger_evidence_id=trigger,
                      supporting=[EvidenceRef(evidence_id=i, note="") for i in support],
                      contradicting=[], assumptions=[], confidence=confidence)


def test_checks_catch_a_trigger_after_onset_and_invented_evidence():
    c = ctx()
    c.evidence.add(EvidenceItem(id="chg-1", source="changes", service="kyc-service",
                                ts=datetime(2026, 10, 3, 14, 0, tzinfo=UTC),
                                summary="deploy", retrieved_by="dependency"))
    hset = HypothesisSet(onset=datetime(2026, 10, 3, 13, 52, tzinfo=UTC), reasoning_summary="",
                         hypotheses=[hypothesis("H1", "kyc-service", "chg-1", ["chg-1"], 0.8),
                                     hypothesis("H2", "ledger-db", None, ["log-99999"], 0.3)])
    flags = check_hypotheses(hset, c)
    assert any("AFTER the symptom onset" in f and "H1" in f for f in flags)
    assert any("never retrieved" in f and "H2" in f for f in flags)
    assert any("health is unverified" in f for f in flags)  # kyc-service never observed
    assert blocking_flags(flags, hset)  # so the Critic may not accept H1


# --- LLM client, router, cache ----------------------------------------------------

def http_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_client_reads_tool_calls_and_counts_reasoning_tokens():
    def handler(request):
        return httpx.Response(200, json={
            "model": "m", "usage": {"prompt_tokens": 100, "completion_tokens": 10,
                                    "total_tokens": 150},
            "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "x", "type": "function", "extra_content": {"google": {"sig": "s"}},
                 "function": {"name": "query_logs", "arguments": '{"service": "a"}'}}]}}]})

    client = OpenAICompatClient(provider="gemini", base_url="http://x", api_key="k", model="m",
                                http=http_client(handler))
    response = await client.chat([{"role": "user", "content": "hi"}])
    assert response.tool_calls[0].arguments == {"service": "a"}
    assert response.completion_tokens == 50  # hidden thinking tokens are billed too
    assert "extra_content" in response.message["tool_calls"][0]  # Gemini needs it echoed


async def test_client_reports_daily_quota_exhaustion():
    def handler(request):
        return httpx.Response(429, text="Quota exceeded: GenerateRequestsPerDayPerProject")

    client = OpenAICompatClient(provider="gemini", base_url="http://x", api_key="k", model="m",
                                http=http_client(handler))
    with pytest.raises(LLMRateLimited) as info:
        await client.chat([{"role": "user", "content": "hi"}])
    assert info.value.daily


async def test_router_falls_back_to_the_next_provider_and_records_usage():
    c = ctx()
    down = ScriptedClient(lambda *a: LLMRateLimited("gemini", None, daily=True))
    up = ScriptedClient(lambda *a: {"content": "{}"}, provider="groq")
    router = Router({"fast": [down, up]})
    response = await router.chat(c, agent="t", tier="fast",
                                 messages=[{"role": "user", "content": "x" * 400}])
    assert response.provider == "groq"
    assert c.budget.llm_calls == 1 and c.budget.prompt_tokens == 100
    await router.chat(c, agent="t", tier="fast", messages=[{"role": "user", "content": "x"}])
    assert down.calls == 1  # a provider out of daily quota is not asked again


async def test_router_waits_on_short_rate_limits():
    c = ctx()
    replies = iter([LLMRateLimited("gemini", 1.0, daily=False), {"content": "ok"}])
    waits: list[float] = []

    async def fake_sleep(s):
        waits.append(s)

    router = Router({"fast": [ScriptedClient(lambda *a: next(replies))]}, sleep=fake_sleep)
    response = await router.chat(c, agent="t", tier="fast", messages=[])
    assert response.content == "ok" and waits == [1.0]


async def test_router_raises_when_every_provider_fails():
    c = ctx()
    router = Router({"fast": [ScriptedClient(lambda *a: LLMError("boom"))]})
    with pytest.raises(LLMError):
        await router.chat(c, agent="t", tier="fast", messages=[])


async def test_cache_replays_answers_and_still_counts_tokens(tmp_path):
    c = ctx()
    client = ScriptedClient(lambda *a: {"content": "same"})
    router = Router({"fast": [client]}, cache=ResponseCache(tmp_path / "c.sqlite"))
    messages = [{"role": "user", "content": "x" * 40}]
    first = await router.chat(c, agent="t", tier="fast", messages=messages)
    second = await router.chat(c, agent="t", tier="fast", messages=messages)
    assert client.calls == 1 and second.cached and not first.cached
    assert c.budget.llm_calls == 2  # cached or not, the run's token count is comparable


async def test_llm_budget_has_a_reserve_for_the_report():
    c = ctx(max_llm_calls=1, reserve_llm_calls=1)
    router = Router({"fast": [ScriptedClient(lambda *a: {"content": "x"})]})
    await router.chat(c, agent="t", tier="fast", messages=[])
    with pytest.raises(BudgetExceeded):
        await router.chat(c, agent="t", tier="fast", messages=[])
    await router.chat(c, agent="reporting", tier="fast", messages=[], use_reserve=True)
