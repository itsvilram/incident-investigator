"""What every investigation run shares: evidence store, budget, trace.

Both the multi-agent system and the single-agent baseline run inside a RunContext,
so they get the same tools, the same limits and the same measurements.
"""

import contextvars
import json
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from investigator.models import EvidenceItem
from investigator.world import World


class BudgetExceeded(Exception):
    """A hard limit was hit. The run stops gathering and goes straight to reporting."""


@dataclass
class Budget:
    max_tool_calls: int = 40
    max_llm_calls: int = 30
    max_tokens: int = 250_000
    max_seconds: float = 600.0
    # Kept back so the final report can still be written when everything else is spent.
    reserve_llm_calls: int = 2
    reserve_tokens: int = 30_000

    tool_calls: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    started: float = field(default_factory=time.monotonic)
    exhausted_reason: str | None = None

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def charge_tool_call(self) -> None:
        if self.tool_calls >= self.max_tool_calls:
            self._exhaust(f"tool-call limit ({self.max_tool_calls})")
        self._check_time()
        self.tool_calls += 1

    def check_llm_call(self, *, use_reserve: bool = False) -> None:
        """Raise if another LLM call is not allowed. The reporter may use the reserve."""
        calls = self.max_llm_calls + (self.reserve_llm_calls if use_reserve else 0)
        tokens = self.max_tokens + (self.reserve_tokens if use_reserve else 0)
        if self.llm_calls >= calls:
            self._exhaust(f"LLM-call limit ({self.max_llm_calls})")
        if self.tokens >= tokens:
            self._exhaust(f"token limit ({self.max_tokens})")
        if not use_reserve:
            self._check_time()

    def record_llm_call(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.llm_calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def _check_time(self) -> None:
        if self.elapsed() > self.max_seconds:
            self._exhaust(f"time limit ({self.max_seconds:.0f}s)")

    def _exhaust(self, reason: str) -> None:
        self.exhausted_reason = self.exhausted_reason or reason
        raise BudgetExceeded(reason)


_current_span: contextvars.ContextVar[str | None] = contextvars.ContextVar("span", default=None)


class Tracer:
    """Spans for every agent step, LLM call and tool call, written as JSONL.

    The parent span travels in a contextvar, so spans opened inside parallel asyncio
    tasks still nest under the agent that started them.
    """

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []
        self._t0 = time.monotonic()

    @contextmanager
    def span(self, kind: str, name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
        span_id = uuid.uuid4().hex[:8]
        record: dict[str, Any] = {
            "id": span_id,
            "parent": _current_span.get(),
            "kind": kind,
            "name": name,
            "start_s": round(time.monotonic() - self._t0, 3),
            **attrs,
        }
        token = _current_span.set(span_id)
        try:
            yield record
            record.setdefault("status", "ok")
        except BaseException as error:
            record["status"] = "error"
            record["error"] = f"{type(error).__name__}: {error}"[:300]
            raise
        finally:
            _current_span.reset(token)
            record["duration_s"] = round(time.monotonic() - self._t0 - record["start_s"], 3)
            self.spans.append(record)

    def event(self, name: str, **attrs: Any) -> None:
        """A point-in-time note (a decision, a retry, a budget stop)."""
        self.spans.append({
            "id": uuid.uuid4().hex[:8], "parent": _current_span.get(), "kind": "event",
            "name": name, "start_s": round(time.monotonic() - self._t0, 3),
            "duration_s": 0, **attrs,
        })

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.spans, key=lambda s: s["start_s"])
        path.write_text("".join(json.dumps(s, default=str) + "\n" for s in ordered))


_SHAPE = re.compile(r"[0-9a-f]*\d[0-9a-f]*")


class EvidenceStore:
    """Everything any tool returned during the run, by evidence ID."""

    def __init__(self) -> None:
        self.items: dict[str, EvidenceItem] = {}

    def add(self, item: EvidenceItem) -> None:
        existing = self.items.get(item.id)
        if existing is None or len(item.summary) > len(existing.summary):
            self.items[item.id] = item

    def has(self, evidence_id: str) -> bool:
        return evidence_id in self.items

    def __len__(self) -> int:
        return len(self.items)

    def digest(self, ids: list[str] | None = None, limit: int = 120) -> str:
        """One line per item for prompts, in time order, capped at `limit`.

        Repeats of the same log message are collapsed: the pattern line (with its count)
        already stands for them, and they would only cost tokens.
        """
        items = [self.items[i] for i in ids if i in self.items] if ids else list(
            self.items.values())
        seen: set[str] = set()
        unique = []
        for e in sorted(items, key=lambda e: "(x" not in e.summary):  # patterns first
            shape = _SHAPE.sub("", e.summary.split(" (x")[0][6:]) if e.source == "logs" else e.id
            if shape not in seen:
                seen.add(shape)
                unique.append(e)
        items = sorted(unique, key=lambda e: (e.ts is None, e.ts))
        if len(items) > limit:
            # Prefer anomalies and errors: they are what investigations hinge on.
            def weight(e: EvidenceItem) -> int:
                text = e.summary
                return (("ERROR" in text) * 3 + ("anomaly" in text) * 3 + ("WARN" in text)
                        + (e.source == "changes") * 2)
            items = sorted(items, key=weight, reverse=True)[:limit]
            items.sort(key=lambda e: (e.ts is None, e.ts))
        return "\n".join(f"[{e.id}] {e.summary}" for e in items)


@dataclass
class RunContext:
    world: World
    budget: Budget = field(default_factory=Budget)
    tracer: Tracer = field(default_factory=Tracer)
    evidence: EvidenceStore = field(default_factory=EvidenceStore)
    gaps: list[str] = field(default_factory=list)  # tool or agent failures, in plain words
    seed: int = 7
    random_fault_rate: float = 0.05
