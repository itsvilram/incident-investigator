"""Settings from environment variables and .env. Every value has a working default."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# OpenAI-compatible endpoints: switching provider is a settings change, not code.
PROVIDER_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1/",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None

    # "provider:model" lists. The first entry is used; the rest are fallbacks when a
    # provider rate-limits or fails. "fast" gathers evidence, "strong" reasons.
    models_fast: str = "gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b"
    models_strong: str = "gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b"

    llm_cache: bool = True
    llm_timeout_s: float = 120.0
    llm_max_concurrency: int = 4  # per provider: free tiers punish bursts

    def api_key(self, provider: str) -> SecretStr | None:
        return {"gemini": self.gemini_api_key, "groq": self.groq_api_key}.get(provider)


@lru_cache
def get_settings() -> Settings:
    return Settings()
