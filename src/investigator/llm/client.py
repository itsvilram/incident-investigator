"""LLM client for any OpenAI-compatible chat API (Gemini, Groq, ...), with tool calling.

One POST to {base_url}/chat/completions over plain HTTP: we control timeouts,
retries and error types. The API key only goes into the Authorization header.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

# "Overloaded, try again soon": two short retries usually turn these into answers.
_RETRY_STATUSES = frozenset({500, 502, 503, 504})
_RETRY_DELAYS_S = (2.0, 5.0)


class LLMError(Exception):
    """The provider failed (network, server error, unreadable answer)."""


class LLMRateLimited(LLMError):
    """HTTP 429. `daily` means the day's quota is gone, so waiting will not help."""

    def __init__(self, provider: str, retry_after_s: float | None, *, daily: bool) -> None:
        super().__init__(f"{provider} is rate limiting us" + (" (daily quota)" if daily else ""))
        self.retry_after_s = retry_after_s
        self.daily = daily


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall]
    message: dict[str, Any]  # the assistant message to append to the conversation
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    latency_s: float
    cached: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class ChatClient(Protocol):
    provider: str
    model: str

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        schema: tuple[str, dict[str, Any]] | None = None,
    ) -> ChatResponse: ...


class OpenAICompatClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 120.0,
        max_concurrency: int = 4,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http = http or httpx.AsyncClient(timeout=timeout_s)
        self._slots = asyncio.Semaphore(max_concurrency)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        schema: tuple[str, dict[str, Any]] | None = None,
    ) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [self._clean(m) for m in messages],
        }
        if tools:
            body["tools"] = tools
        if schema:
            name, json_schema = schema
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": json_schema, "strict": True},
            }
        started = time.monotonic()
        async with self._slots:
            response = await self._post(body)
        latency = time.monotonic() - started
        if response.status_code == 429:
            raise LLMRateLimited(self.provider, _seconds(response.headers.get("retry-after")),
                                 daily="perday" in response.text.lower().replace(" ", ""))
        if response.status_code >= 400:
            raise LLMError(f"{self.provider} answered HTTP {response.status_code}: "
                           f"{response.text[:300]}")
        return self._read(response, latency)

    def _clean(self, message: dict[str, Any]) -> dict[str, Any]:
        """Keep the fields chat APIs accept. Gemini needs its thought signatures echoed
        back on tool calls; other providers may reject that extra field."""
        out = {k: v for k, v in message.items()
               if k in ("role", "content", "tool_calls", "tool_call_id", "name")}
        if self.provider != "gemini" and "tool_calls" in out:
            out["tool_calls"] = [{k: v for k, v in tc.items() if k != "extra_content"}
                                 for tc in out["tool_calls"]]
        if out.get("content") is None and out["role"] == "assistant":
            out["content"] = ""
        return out

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        for delay in (*_RETRY_DELAYS_S, None):
            try:
                response = await self._http.post(self._url, json=body, headers=self._headers)
            except httpx.HTTPError as error:
                if delay is None:
                    raise LLMError(f"Could not reach {self.provider} "
                                   f"({type(error).__name__})") from error
                await asyncio.sleep(delay)
                continue
            if response.status_code not in _RETRY_STATUSES or delay is None:
                return response
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    def _read(self, response: httpx.Response, latency: float) -> ChatResponse:
        try:
            data = response.json()
            message = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            calls = [
                ToolCall(
                    id=tc.get("id") or f"call_{i}",
                    name=tc["function"]["name"],
                    arguments=_parse_args(tc["function"].get("arguments")),
                )
                for i, tc in enumerate(message.get("tool_calls") or [])
            ]
            prompt = int(usage.get("prompt_tokens", 0))
            total = int(usage.get("total_tokens", 0))
            # Count hidden reasoning ("thinking") tokens as completion tokens: we pay for them.
            completion = max(int(usage.get("completion_tokens", 0)), total - prompt)
            kept = {"role": "assistant", "content": message.get("content")}
            if message.get("tool_calls"):
                kept["tool_calls"] = message["tool_calls"]
            return ChatResponse(
                content=message.get("content"), tool_calls=calls, message=kept,
                prompt_tokens=prompt, completion_tokens=completion,
                model=str(data.get("model", self.model)), provider=self.provider,
                latency_s=latency,
            )
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"Unreadable answer from {self.provider}: "
                           f"{response.text[:300]}") from error

    async def aclose(self) -> None:
        await self._http.aclose()


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparseable": str(raw)[:200]}
    return value if isinstance(value, dict) else {}


def _seconds(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
