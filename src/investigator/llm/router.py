"""Model routing: pick a model by tier, fall back across providers, account for every call.

Agents ask for a tier ("fast" or "strong"), never a vendor. The router:
  - checks the run's budget before the call (the reporter may use a reserve),
  - serves a cached answer when the exact request was seen before,
  - on a rate limit, waits (bounded) and retries, then falls back to the next provider;
    a provider whose daily quota is gone is skipped for the rest of the process,
  - records tokens in the budget and a span in the trace.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from investigator.config import PROJECT_ROOT, PROVIDER_BASE_URLS, Settings
from investigator.harness.context import RunContext
from investigator.llm.cache import ResponseCache, cache_key
from investigator.llm.client import (
    ChatClient,
    ChatResponse,
    LLMError,
    LLMRateLimited,
    OpenAICompatClient,
)


class Router:
    def __init__(
        self,
        tiers: dict[str, list[ChatClient]],
        *,
        cache: ResponseCache | None = None,
        rate_limit_waits: int = 2,
        max_wait_s: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.tiers = tiers
        self.cache = cache
        self._rate_limit_waits = rate_limit_waits
        self._max_wait_s = max_wait_s
        self._sleep = sleep
        self._exhausted: set[int] = set()  # clients whose daily quota is gone
        # Calls that fell back to another model or failed on rate limits. The eval's strict
        # mode discards runs where this grew, so every scored run used the intended model.
        self.degraded_calls = 0

    def describe(self) -> dict[str, list[str]]:
        return {tier: [f"{c.provider}:{c.model}" for c in clients]
                for tier, clients in self.tiers.items()}

    async def chat(
        self,
        ctx: RunContext,
        *,
        agent: str,
        tier: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        schema: tuple[str, dict[str, Any]] | None = None,
        use_reserve: bool = False,
    ) -> ChatResponse:
        ctx.budget.check_llm_call(use_reserve=use_reserve)
        clients = [c for c in self.tiers[tier] if id(c) not in self._exhausted]
        if not clients:
            raise LLMError(f"Every provider for tier {tier!r} is out of quota today.")

        with ctx.tracer.span("llm", f"{agent}:{tier}", agent=agent) as span:
            key = None
            response = None
            if self.cache is not None:
                key = cache_key(clients[0].provider, clients[0].model, messages, tools, schema)
                response = self.cache.get(key)
            if response is None:
                response = await self._call(clients, messages, tools, schema, ctx, span)
                if self.cache is not None and key is not None:
                    self.cache.put(key, response)
            ctx.budget.record_llm_call(response.prompt_tokens, response.completion_tokens)
            span.update(
                provider=response.provider, model=response.model, cached=response.cached,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                llm_latency_s=round(response.latency_s, 3),
                tool_calls=[tc.name for tc in response.tool_calls],
            )
            return response

    async def _call(self, clients, messages, tools, schema, ctx: RunContext,
                    span: dict[str, Any]) -> ChatResponse:
        errors: list[str] = []
        for i, client in enumerate(clients):
            if i > 0:
                ctx.tracer.event("llm_fallback", to=f"{client.provider}:{client.model}",
                                 reason=errors[-1][:200])
                span["fallback"] = True
                self.degraded_calls += 1
            for wait in range(self._rate_limit_waits + 1):
                try:
                    return await client.chat(messages, tools=tools, schema=schema)
                except LLMRateLimited as error:
                    if error.daily:
                        self._exhausted.add(id(client))
                        errors.append(str(error))
                        break
                    if wait == self._rate_limit_waits:
                        errors.append(str(error))
                        break
                    delay = min(error.retry_after_s or 10.0 * (wait + 1), self._max_wait_s)
                    ctx.tracer.event("llm_rate_limited", provider=client.provider,
                                     wait_s=delay)
                    await self._sleep(delay)
                except LLMError as error:
                    errors.append(str(error))
                    break
        if any("rate limiting" in e for e in errors):
            self.degraded_calls += 1
        raise LLMError("All providers failed: " + " | ".join(e[:200] for e in errors))


def build_router(settings: Settings, *, use_cache: bool | None = None) -> Router:
    """Real clients for every configured provider that has an API key."""
    shared: dict[str, OpenAICompatClient] = {}

    def client(entry: str) -> OpenAICompatClient | None:
        provider, _, model = entry.strip().partition(":")
        key = settings.api_key(provider)
        if key is None or not key.get_secret_value() or provider not in PROVIDER_BASE_URLS:
            return None
        if entry not in shared:
            shared[entry] = OpenAICompatClient(
                provider=provider, base_url=PROVIDER_BASE_URLS[provider],
                api_key=key.get_secret_value(), model=model,
                timeout_s=settings.llm_timeout_s, max_concurrency=settings.llm_max_concurrency,
            )
        return shared[entry]

    tiers: dict[str, list[ChatClient]] = {}
    for tier, spec in (("fast", settings.models_fast), ("strong", settings.models_strong)):
        tiers[tier] = [c for e in spec.split(",") if e.strip() and (c := client(e))]
        if not tiers[tier]:
            raise RuntimeError(f"No usable model for tier {tier!r}: set GEMINI_API_KEY or "
                               "GROQ_API_KEY in .env (see .env.example).")
    cache_on = settings.llm_cache if use_cache is None else use_cache
    cache = ResponseCache(PROJECT_ROOT / ".cache" / "llm.sqlite") if cache_on else None
    return Router(tiers, cache=cache)
