"""Tools return structured, evidence-tagged results and fail the way we scripted."""

import pytest

from investigator.harness.context import Budget, BudgetExceeded, RunContext
from investigator.tools.executor import FaultInjector, ToolExecutor
from investigator.world import World


def executor(incident_id: str, *, rate: float = 0.0, budget: Budget | None = None):
    ctx = RunContext(world=World.load(incident_id), random_fault_rate=rate,
                     budget=budget or Budget())
    return ctx, ToolExecutor(ctx, timeout_s=0.05, backoff_s=0.0)


async def test_logs_are_grouped_into_patterns_with_first_seen():
    ctx, tools = executor("INC-02")
    result = await tools.call("observability", "query_logs",
                              {"service": "ledger-db", "level": "ERROR"})
    assert result["status"] == "ok"
    top = result["patterns"][0]
    assert "No space left on device" in top["example"]
    assert top["first_seen"].startswith("2026-10-03T13:52")
    assert ctx.evidence.has(top["first_id"])
    assert ctx.evidence.items[top["first_id"]].retrieved_by == "observability"


async def test_metrics_report_anomaly_onset_and_saturation():
    _, tools = executor("INC-02")
    result = await tools.call("observability", "query_metrics",
                              {"service": "ledger-db",
                               "metrics": ["error_rate_pct", "disk_used_pct"]})
    by_name = {m["metric"]: m for m in result["metrics"]}
    assert by_name["error_rate_pct"]["anomaly"]["started_at"].startswith("2026-10-03T13:52")
    assert by_name["disk_used_pct"]["saturated"] is True


async def test_scripted_timeouts_are_retried_then_reported_as_a_gap():
    ctx, tools = executor("INC-07")  # first 3 metric calls for orders-service time out
    first = await tools.call("observability", "query_metrics", {"service": "orders-service"})
    assert first["status"] == "error" and first["retryable"] is True
    assert ctx.budget.tool_calls == 3  # every attempt counts
    assert any("timed out" in gap for gap in ctx.gaps)
    second = await tools.call("observability", "query_metrics", {"service": "orders-service"})
    assert second["status"] == "ok"


async def test_partial_results_are_flagged():
    ctx, tools = executor("INC-07")
    result = await tools.call("observability", "query_logs", {"service": "orders-service"})
    assert result["status"] == "partial"
    assert "INCOMPLETE" in result["note"]
    assert any("partial" in gap for gap in ctx.gaps)


async def test_persistent_outage_never_succeeds():
    _, tools = executor("INC-09")
    for _ in range(2):
        result = await tools.call("observability", "query_metrics",
                                  {"service": "notification-service"})
        assert result["status"] == "error"
        assert "503" in result["error"]


async def test_bad_input_is_a_structured_error_not_an_exception():
    ctx, tools = executor("INC-01")
    unknown = await tools.call("observability", "query_logs", {"service": "nope"})
    assert unknown["status"] == "error" and unknown["retryable"] is False
    invalid = await tools.call("observability", "query_metrics", {"metrics": ["rps"]})
    assert "Invalid arguments" in invalid["error"]
    missing = await tools.call("observability", "no_such_tool", {})
    assert missing["status"] == "error"
    assert ctx.gaps == []


async def test_budget_stops_tool_calls():
    _, tools = executor("INC-01", budget=Budget(max_tool_calls=1))
    await tools.call("dependency", "get_deployments", {})
    with pytest.raises(BudgetExceeded):
        await tools.call("dependency", "get_deployments", {})


def test_random_faults_depend_on_the_call_not_the_order():
    ctx = RunContext(world=World.load("INC-01"), random_fault_rate=0.5, seed=3)
    calls = [("query_logs", {"service": s}) for s in ("payments-api", "mobile-bff", "kyc-service")]
    a = [FaultInjector(ctx).decide(t, args, 1) for t, args in calls]
    b = [FaultInjector(ctx).decide(t, args, 1) for t, args in reversed(calls)]
    assert a == list(reversed(b))


async def test_dependencies_walk_two_hops():
    _, tools = executor("INC-03")
    result = await tools.call("dependency", "get_service_dependencies",
                              {"service": "payments-api", "direction": "dependencies"})
    edges = {e["id"] for e in result["edges"]}
    assert "dep:upi-gateway->partner-bank-api" in edges


async def test_history_search_ranks_similar_incidents():
    _, tools = executor("INC-05")
    result = await tools.call("reasoning", "search_past_incidents",
                              {"query": "users cannot link bank accounts account aggregator"})
    assert result["matches"][0]["id"] == "hist-2026-0907"
