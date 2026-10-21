"""A scripted chat client for tests: no network, no key, fully deterministic.

The policy function sees what a real model would see (messages, tools, schema) and
returns either tool calls or content. Tests use it to drive the real harness, agents
and tools end to end.
"""

import json
from collections.abc import Callable
from typing import Any

from investigator.llm.client import ChatResponse, ToolCall

type Policy = Callable[[list[dict[str, Any]], list[dict[str, Any]] | None,
                        tuple[str, Any] | None], dict[str, Any] | Exception]


class ScriptedClient:
    def __init__(self, policy: Policy, *, provider: str = "fake", model: str = "scripted"):
        self.provider = provider
        self.model = model
        self.policy = policy
        self.calls = 0

    async def chat(self, messages, *, tools=None, schema=None) -> ChatResponse:
        self.calls += 1
        out = self.policy(messages, tools, schema)
        if isinstance(out, Exception):
            raise out
        calls = [ToolCall(id=f"call_{self.calls}_{i}", name=name, arguments=args)
                 for i, (name, args) in enumerate(out.get("tool_calls", []))]
        message: dict[str, Any] = {"role": "assistant", "content": out.get("content")}
        if calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in calls
            ]
        prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
        return ChatResponse(content=out.get("content"), tool_calls=calls, message=message,
                            prompt_tokens=prompt_chars // 4, completion_tokens=40,
                            model=self.model, provider=self.provider, latency_s=0.0)
