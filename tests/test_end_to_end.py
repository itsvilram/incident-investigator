"""Whole investigations with a scripted LLM: real harness, agents, tools and data.

The script plays each agent generically (call a tool, then answer citing whatever IDs
it saw). It is not told the answer. These tests check the machinery: the feedback
loop, recovery from failures, budgets and the report, not the model's judgement.
"""

import json
import re

from investigator import baseline, multi_agent
from investigator.harness.context import Budget
from investigator.llm.client import LLMError
from investigator.llm.fake import ScriptedClient
from investigator.llm.router import Router
from investigator.runs import save_run
from investigator.world import World

ID = re.compile(r"(log-\d{5}|metric:[a-z-]+:[a-z_]+|chg-\d{4})")


def role(messages) -> str:
    system = messages[0]["content"]
    for name in ("Orchestrator", "Observability", "Dependency", "Reasoning", "Critic",
                 "Reporting"):
        if f"the {name}" in system or f"You are the {name}" in system:
            return name.lower()
    return "baseline"


def generic_policy(*, critic_rounds_before_accept: int = 1, fail: set[str] = frozenset(),
                   same_queries: bool = False):
    def policy(messages, tools, schema):
        who = role(messages)
        if who in fail:
            return LLMError(f"{who} is down")
        transcript = json.dumps(messages[1:])  # not the system prompt's example IDs
        seen = list(dict.fromkeys(ID.findall(transcript)))
        if tools:
            if any(m["role"] == "tool" for m in messages):
                return {"content": "done"}
            if who == "dependency":
                return {"tool_calls": [("get_deployments", {}),
                                       ("get_service_dependencies", {"service": "payments-api"})]}
            if who == "reasoning":
                return {"tool_calls": [("search_past_incidents", {"query": "payments pending"})]}
            # each round looks at another service, so every round finds new evidence
            current = re.search(r"YOUR TASK \(r(\d+)-", transcript)
            n = int(current.group(1)) if current and not same_queries else 1
            service = ["ledger-db", "ledger-service", "payments-api"][(n - 1) % 3]
            return {"tool_calls": [("query_logs", {"service": service, "level": "ERROR"}),
                                   ("query_metrics", {"service": service})]}
        name = schema[0]
        cite = seen[:2] or ["log-00001"]
        if name == "InvestigationPlan":
            return {"content": json.dumps({"rationale": "r", "stop": False, "tasks": [
                {"agent": "observability", "goal": "errors?", "services": ["ledger-db"]},
                {"agent": "dependency", "goal": "changes?", "services": ["payments-api"]}]})}
        if name == "AgentFindings":
            return {"content": json.dumps({"summary": "s", "suspected_services": ["ledger-db"],
                                           "open_questions": [], "findings": [
                {"statement": "errors", "kind": "fact", "evidence_ids": cite,
                 "service": "ledger-db"}]})}
        if name == "HypothesisSet":
            return {"content": json.dumps({"onset": "2026-10-03T13:52:00Z",
                                           "reasoning_summary": "s", "hypotheses": [
                {"id": "H1", "title": "disk full", "root_cause_service": "ledger-db",
                 "category": "resource_exhaustion", "mechanism": "m",
                 "trigger_evidence_id": None, "assumptions": [], "confidence": 0.8,
                 "supporting": [{"evidence_id": i, "note": "n"} for i in cite],
                 "contradicting": []}]})}
        if name == "Critique":
            current = int(re.search(r"This is round (\d+)", transcript).group(1))
            more = current <= critic_rounds_before_accept
            return {"content": json.dumps({
                "verdict": "investigate_more" if more else "accept", "issues": [],
                "adjustments": [],
                "requests": [{"agent": "observability", "goal": "disk?",
                              "services": ["ledger-db"], "reason": "r"}] if more else []})}
        if name == "FinalReport":
            return {"content": json.dumps({
                "verdict": "root_cause_identified", "summary": "disk full",
                "ranked_hypotheses": [{"rank": 1, "title": "disk full",
                                       "root_cause_service": "ledger-db",
                                       "category": "resource_exhaustion", "confidence": 0.8,
                                       "supporting": [{"evidence_id": cite[0], "note": "n"}],
                                       "contradicting": []}],
                "facts": [{"text": "errors", "evidence_ids": cite}], "assumptions": [],
                "evidence_gaps": [], "timeline": [], "recommended_actions": []})}
        raise AssertionError(name)
    return policy


def router(policy) -> Router:
    client = ScriptedClient(policy)
    return Router({"fast": [client], "strong": [client]})


async def test_multi_agent_runs_the_feedback_loop_and_reports(tmp_path):
    world = World.load("INC-02")
    result, state = await multi_agent.investigate(world, router(generic_policy()),
                                                  fault_rate=0.0)
    assert state.round == 2  # round 1 critique asked for more; round 2 accepted
    assert result.stop_reason == "critic accepted the top hypothesis"
    assert [t.id for t in state.tasks if t.agent == "observability"][-1].startswith("r2-")
    assert result.report.ranked_hypotheses[0].root_cause_service == "ledger-db"
    assert set(result.cited_ids) <= set(result.retrieved_ids)
    folder = save_run(result, state.ctx, tmp_path, multi_agent.state_snapshot(state))
    assert {"report.md", "result.json", "trace.jsonl", "state.json"} <= {
        p.name for p in folder.iterdir()}
    kinds = {json.loads(line)["kind"] for line in (folder / "trace.jsonl").open()}
    assert {"run", "task", "agent", "llm", "tool"} <= kinds


async def test_round_limit_forces_a_decision():
    world = World.load("INC-02")
    result, state = await multi_agent.investigate(
        world, router(generic_policy(critic_rounds_before_accept=99)), fault_rate=0.0)
    assert state.round == 3
    assert state.latest_critique.verdict == "inconclusive"  # never "investigate_more" at the end
    assert result.report.verdict == "inconclusive"


async def test_a_round_without_new_evidence_ends_the_investigation():
    world = World.load("INC-02")
    result, state = await multi_agent.investigate(
        world, router(generic_policy(critic_rounds_before_accept=99, same_queries=True)),
        fault_rate=0.0)
    assert state.round == 2
    assert result.stop_reason == "the last round found no new evidence"


async def test_orchestrator_and_reporter_failures_fall_back_to_code():
    world = World.load("INC-02")
    result, state = await multi_agent.investigate(
        world, router(generic_policy(fail={"orchestrator", "reporting"})), fault_rate=0.0)
    assert state.plans[0].rationale.startswith("Default plan")
    assert result.report.ranked_hypotheses  # built from the shared state by code
    assert any("orchestrator failed" in g for g in result.gaps)


async def test_budget_exhaustion_still_produces_a_report():
    world = World.load("INC-02")
    result, _ = await multi_agent.investigate(world, router(generic_policy()),
                                              budget=Budget(max_tool_calls=3), fault_rate=0.0)
    assert result.stop_reason.startswith("budget exhausted")
    assert result.report is not None and result.tool_calls <= 3


async def test_baseline_uses_the_same_tools_and_report_format():
    world = World.load("INC-02")
    result, _ = await baseline.investigate(world, router(generic_policy()), fault_rate=0.0)
    assert result.system == "baseline" and result.tool_calls == 2
    assert result.report.ranked_hypotheses[0].root_cause_service == "ledger-db"
