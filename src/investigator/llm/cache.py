"""A disk cache of LLM responses (SQLite), keyed by the exact request.

Same model + same messages + same tools/schema = same answer, so re-running an
investigation or resuming an interrupted eval costs no quota. Turn it off
(LLM_CACHE=false) for runs whose latency you want to report.
"""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from investigator.llm.client import ChatResponse, ToolCall


def cache_key(provider: str, model: str, messages: list[dict[str, Any]],
              tools: list[dict[str, Any]] | None, schema: tuple[str, Any] | None) -> str:
    payload = json.dumps([provider, model, messages, tools, schema], sort_keys=True,
                         default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, "
                         "value TEXT NOT NULL)")

    def get(self, key: str) -> ChatResponse | None:
        row = self._db.execute("SELECT value FROM responses WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        data["tool_calls"] = [ToolCall(**tc) for tc in data["tool_calls"]]
        data["cached"] = True
        return ChatResponse(**data)

    def put(self, key: str, response: ChatResponse) -> None:
        data = asdict(response)
        data["cached"] = False
        self._db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?)",
                         (key, json.dumps(data)))
        self._db.commit()
