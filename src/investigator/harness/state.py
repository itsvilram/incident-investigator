"""The shared investigation state (the team's whiteboard).

Agents never talk to each other directly. They read from this state and write typed
results into it: findings per task, the current hypotheses, critiques, the code
check results. The Orchestrator reads it to plan the next round.
"""

from dataclasses import dataclass, field
from typing import Literal

from investigator.harness.context import RunContext
from investigator.models import (
    AgentFindings,
    Critique,
    HypothesisSet,
    InvestigationPlan,
    PlannedTask,
)

type TaskStatus = Literal["pending", "running", "done", "failed", "skipped"]


@dataclass
class Task:
    id: str
    agent: str  # observability | dependency | reasoning | critic
    goal: str
    services: list[str]
    round: int
    depends_on: list[str] = field(default_factory=list)  # wait for these (any outcome)
    requires: list[str] = field(default_factory=list)  # skip this task if any of these failed
    created_by: str = "orchestrator"
    status: TaskStatus = "pending"
    attempts: int = 0
    max_attempts: int = 2
    error: str | None = None


@dataclass
class InvestigationState:
    ctx: RunContext
    tasks: list[Task] = field(default_factory=list)
    findings: dict[str, AgentFindings] = field(default_factory=dict)  # by task id
    hypotheses: HypothesisSet | None = None
    critiques: dict[int, Critique] = field(default_factory=dict)  # by round
    check_flags: list[str] = field(default_factory=list)  # latest code checks
    plans: list[InvestigationPlan] = field(default_factory=list)
    round: int = 0
    stop_reason: str | None = None

    @property
    def incident(self):
        return self.ctx.world.incident

    @property
    def latest_critique(self) -> Critique | None:
        return self.critiques[max(self.critiques)] if self.critiques else None

    def schedule_round(self, planned: list[PlannedTask]) -> list[Task]:
        """Evidence tasks run in parallel; Reasoning waits for all of them; the Critic
        needs Reasoning to have succeeded."""
        r = self.round
        evidence = [
            Task(id=f"r{r}-{p.agent}-{i}", agent=p.agent, goal=p.goal, services=p.services,
                 round=r)
            for i, p in enumerate(planned, 1)
        ]
        reasoning = Task(id=f"r{r}-reasoning", agent="reasoning",
                         goal="Build and rank competing root-cause hypotheses", services=[],
                         round=r, depends_on=[t.id for t in evidence])
        critic = Task(id=f"r{r}-critic", agent="critic", goal="Challenge the hypotheses",
                      services=[], round=r, requires=[reasoning.id])
        new = [*evidence, reasoning, critic]
        self.tasks.extend(new)
        return new

    def findings_text(self) -> str:
        if not self.findings:
            return "(no findings yet)"
        blocks = []
        for task in self.tasks:
            f = self.findings.get(task.id)
            if f is None:
                continue
            lines = [f"[{task.id}] {task.agent}: {task.goal}", f"  summary: {f.summary}"]
            lines += [f"  - ({x.kind}) {x.statement} {x.evidence_ids}" for x in f.findings]
            if f.open_questions:
                lines.append(f"  open questions: {'; '.join(f.open_questions)}")
            blocks.append("\n".join(lines))
        failed = [t for t in self.tasks if t.status in ("failed", "skipped")]
        blocks += [f"[{t.id}] {t.agent} task {t.status}: {t.goal} ({t.error})" for t in failed]
        return "\n\n".join(blocks)

    def hypotheses_text(self) -> str:
        if not self.hypotheses or not self.hypotheses.hypotheses:
            return "(no hypotheses yet)"
        h = self.hypotheses
        out = [f"Onset per evidence: {h.onset.isoformat() if h.onset else 'not established'}"]
        for x in h.hypotheses:
            out.append(
                f"{x.id} [{x.confidence:.2f}] {x.title} | service={x.root_cause_service} "
                f"category={x.category} trigger={x.trigger_evidence_id}\n"
                f"   mechanism: {x.mechanism}\n"
                f"   supporting: {[(r.evidence_id, r.note) for r in x.supporting]}\n"
                f"   contradicting: {[(r.evidence_id, r.note) for r in x.contradicting]}\n"
                f"   assumptions: {x.assumptions}"
            )
        out.append(f"Reasoning summary: {h.reasoning_summary}")
        return "\n".join(out)

    def gaps_text(self) -> str:
        return "\n".join(f"- {g}" for g in dict.fromkeys(self.ctx.gaps)) or "(none)"

    def tasks_text(self) -> str:
        return "\n".join(f"- {t.id} [{t.status}] {t.agent}: {t.goal} {t.services}"
                         for t in self.tasks if t.agent in ("observability", "dependency"))
