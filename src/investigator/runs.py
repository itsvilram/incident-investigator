"""The outcome of one investigation, the same shape for both systems, and saving it."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from investigator.agents.reporting import cited_ids, render_markdown
from investigator.harness.context import RunContext
from investigator.models import FinalReport


@dataclass
class RunResult:
    system: str  # "multi_agent" | "baseline"
    incident_id: str
    report: FinalReport
    stop_reason: str
    rounds: int
    tool_calls: int
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    retrieved_ids: list[str]
    cited_ids: list[str]
    gaps: list[str]
    models: dict[str, list[str]] = field(default_factory=dict)
    rate_limit_wait_s: float = 0.0  # time spent waiting on provider rate limits (in latency)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def from_context(cls, system: str, ctx: RunContext, report: FinalReport, *,
                     stop_reason: str, rounds: int, latency_s: float,
                     models: dict[str, list[str]]) -> "RunResult":
        b = ctx.budget
        return cls(
            system=system, incident_id=ctx.world.incident.id, report=report,
            stop_reason=stop_reason, rounds=rounds, tool_calls=b.tool_calls,
            llm_calls=b.llm_calls, prompt_tokens=b.prompt_tokens,
            completion_tokens=b.completion_tokens, latency_s=round(latency_s, 2),
            retrieved_ids=sorted(ctx.evidence.items), cited_ids=cited_ids(report),
            gaps=list(dict.fromkeys(ctx.gaps)), models=models,
            rate_limit_wait_s=rate_limit_wait(ctx.tracer.spans),
        )

    def to_json(self) -> dict:
        data = asdict(self)
        data["report"] = self.report.model_dump(mode="json")
        data["total_tokens"] = self.total_tokens
        return data


def rate_limit_wait(spans: list[dict]) -> float:
    return round(sum(s.get("wait_s", 0) for s in spans if s["name"] == "llm_rate_limited"), 1)


def save_run(result: RunResult, ctx: RunContext, out_dir: Path,
             extra_state: dict | None = None) -> Path:
    folder = out_dir / result.system / result.incident_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "result.json").write_text(json.dumps(result.to_json(), indent=1, default=str))
    meta = {"system": result.system, "stop": result.stop_reason, "rounds": result.rounds,
            "tool calls": result.tool_calls, "LLM calls": result.llm_calls,
            "tokens": result.total_tokens, "latency": f"{result.latency_s}s"}
    title = f"{result.incident_id}: {ctx.world.incident.title}"
    (folder / "report.md").write_text(render_markdown(result.report, title=title, meta=meta),
                                      encoding="utf-8")
    ctx.tracer.dump(folder / "trace.jsonl")
    if extra_state is not None:
        (folder / "state.json").write_text(json.dumps(extra_state, indent=1, default=str))
    return folder
