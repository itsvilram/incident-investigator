"""Shared types: what tools, agents and the harness pass to each other.

Every agent output is one of these Pydantic models, so agents exchange validated,
structured results, never free text. The same classes give the JSON schemas the
LLM must answer in (see llm/schema.py).

Evidence IDs are the glue. Every item a tool returns has an ID (a log line
"log-0412", a metric "metric:ledger-db:disk_used_pct", a change "chg-1042", ...).
Findings, hypotheses and the final report cite those IDs, and the harness checks
that every cited ID was really retrieved during the investigation.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The root-cause classes the system can conclude. Scoring compares (service, category).
type RootCauseCategory = Literal[
    "bad_deploy",  # a code release broke something
    "config_change",  # a configuration change (no new code)
    "feature_flag",  # a flag turned on a code path
    "dependency_failure",  # an internal dependency (DB, cache, service) failed
    "third_party_outage",  # an external vendor or partner failed
    "resource_exhaustion",  # disk, memory, connections or threads ran out
    "traffic_spike",  # load beyond capacity
    "certificate_expiry",
    "network_dns",
    "unknown",
]

type AgentName = Literal[
    "orchestrator", "observability", "dependency", "reasoning", "critic", "reporting"
]


class Strict(BaseModel):
    """Base for models the LLM fills in: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


# --- The incident and the world -------------------------------------------------


class IncidentReport(BaseModel):
    """What the on-call engineer wrote. May contain wrong guesses."""

    id: str
    title: str
    reported_at: datetime
    reporter: str
    description: str
    symptom_services: list[str]
    customer_impact: str


class EvidenceItem(BaseModel):
    """One retrieved fact, kept in the shared evidence store under its ID."""

    id: str
    source: Literal["logs", "metrics", "changes", "topology", "history"]
    service: str | None
    ts: datetime | None
    summary: str  # one line, used in prompts
    retrieved_by: str  # agent (or "baseline") whose tool call returned it


# --- Agent outputs ---------------------------------------------------------------


class Finding(Strict):
    statement: str
    kind: Literal["fact", "inference"] = Field(
        description="fact = directly shown by the cited evidence; inference = your interpretation"
    )
    evidence_ids: list[str]
    service: str | None


class AgentFindings(Strict):
    """What the Observability and Dependency agents hand back."""

    summary: str
    findings: list[Finding]
    suspected_services: list[str]
    open_questions: list[str] = Field(description="What you could not establish, and why")


class EvidenceRef(Strict):
    evidence_id: str
    note: str = Field(description="How this evidence supports or contradicts the hypothesis")


class Hypothesis(Strict):
    id: str = Field(description="H1, H2, ... stable across rounds for the same idea")
    title: str
    root_cause_service: str = Field(description="The service where the fault originates")
    category: RootCauseCategory
    mechanism: str = Field(description="Causal chain from root cause to the reported symptoms")
    trigger_evidence_id: str | None = Field(
        description="The change or event that started it, if any (e.g. a chg-... ID)"
    )
    supporting: list[EvidenceRef]
    contradicting: list[EvidenceRef]
    assumptions: list[str] = Field(description="What must be true but is not shown by evidence")
    confidence: float = Field(ge=0, le=1)


class HypothesisSet(Strict):
    """The Reasoning agent's output: competing hypotheses, best first."""

    onset: datetime | None = Field(description="When the symptoms began, per the evidence")
    hypotheses: list[Hypothesis]
    reasoning_summary: str


class EvidenceRequest(Strict):
    """A request for more evidence: the Critic asks, the Orchestrator schedules."""

    agent: Literal["observability", "dependency"]
    goal: str = Field(description="The specific question to answer")
    services: list[str]
    reason: str


class ConfidenceAdjustment(Strict):
    hypothesis_id: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class Critique(Strict):
    verdict: Literal["accept", "investigate_more", "inconclusive"]
    issues: list[str]
    requests: list[EvidenceRequest]
    adjustments: list[ConfidenceAdjustment]


class PlannedTask(Strict):
    agent: Literal["observability", "dependency"]
    goal: str
    services: list[str]


class InvestigationPlan(Strict):
    """The Orchestrator's plan for one round of evidence gathering."""

    rationale: str
    tasks: list[PlannedTask]
    stop: bool = Field(description="True if more evidence gathering would not help")


# --- The final report --------------------------------------------------------------


class RankedHypothesis(Strict):
    rank: int
    title: str
    root_cause_service: str
    category: RootCauseCategory
    confidence: float = Field(ge=0, le=1)
    supporting: list[EvidenceRef]
    contradicting: list[EvidenceRef]


class Statement(Strict):
    text: str
    evidence_ids: list[str]


class TimelineEntry(Strict):
    ts: datetime
    event: str
    evidence_id: str | None


class Action(Strict):
    action: str
    priority: Literal["immediate", "short_term", "long_term"]
    rationale: str
    evidence_ids: list[str]


class FinalReport(Strict):
    verdict: Literal["root_cause_identified", "inconclusive"]
    summary: str
    ranked_hypotheses: list[RankedHypothesis]
    facts: list[Statement] = Field(description="Only what the cited evidence directly shows")
    assumptions: list[str] = Field(description="Beliefs the conclusion rests on that are unproven")
    evidence_gaps: list[str] = Field(description="Data that was missing or tools that failed")
    timeline: list[TimelineEntry]
    recommended_actions: list[Action]
