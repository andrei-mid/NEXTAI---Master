"""Settings from environment / .env. Every variable is documented in .env.example.

Configuration over code: weights, thresholds, time budgets, TTLs and model names live
here or in config files, never hard-coded in agents.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- modes
    fixture_mode: bool = True
    fixtures_dir: Path = REPO_ROOT / "fixtures"
    environment: Literal["local", "demo", "aws"] = "local"

    # --- logging
    log_level: str = "INFO"
    log_json: bool = True

    # --- infrastructure backends (ports -> implementations)
    queue_backend: Literal["memory", "redis", "sqs"] = "memory"
    cache_backend: Literal["memory", "redis"] = "memory"
    object_store_backend: Literal["filesystem", "s3"] = "filesystem"
    rate_limiter_backend: Literal["memory", "redis"] = "memory"
    repository_backend: Literal["memory", "postgres"] = "memory"

    # D5: PostgreSQL 17 (AWS RDS in the cloud, the same version in Docker locally).
    database_url: str = "postgresql+asyncpg://verifirm:verifirm@localhost:5432/verifirm"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_s: float = 30.0
    db_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    sqs_queue_url: str | None = None
    s3_bucket: str | None = None
    object_store_path: Path = REPO_ROOT / ".data" / "objects"
    aws_region: str = "eu-central-1"

    # --- pipeline
    agent_timeout_s: float = 60.0
    agent_timeouts_s: dict[str, float] = Field(default_factory=dict)  # per-agent override, JSON
    mirror_max_age_s: int = (
        86_400  # mirror copies older than this are "stale" (sync refreshes them)
    )
    mirror_max_age_overrides_s: dict[str, int] = Field(default_factory=dict)  # per-adapter, JSON
    sync_timeout_s: float = 180.0  # per adapter, for the pipeline sync step and sync jobs
    # new applications and rechecks download once before agents run
    sync_on_application: bool = True
    # run the queue consumer inside the API process (single box / local dev)
    embedded_worker: bool = False
    http_timeout_s: float = 20.0
    http_max_retries: int = 3
    scoring_config_path: Path = REPO_ROOT / "verifirm" / "scoring" / "config" / "weights.yaml"

    # --- LLM (D3: default Claude direct API; bedrock / openai / openai_compatible / fake)
    llm_provider: Literal["anthropic", "bedrock", "openai", "openai_compatible", "fake"] = (
        "anthropic"
    )
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_compatible_base_url: str | None = None  # e.g. Featherless
    openai_compatible_api_key: str | None = None
    llm_model_default: str = "claude-sonnet-5-5"
    llm_model_memo: str | None = None
    llm_model_critic: str | None = None
    llm_model_classify: str | None = None
    llm_model_analyst: str | None = None  # AI analyst opinion (docs/DECISIONS.md)
    analyst_enabled: bool = True  # run the AI analyst step after scoring (one LLM call per run)

    # --- web search (D10: Tavily)
    web_search_provider: Literal["tavily", "fixture"] = "tavily"
    tavily_api_key: str | None = None

    # --- API
    api_cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    fixture_sse_delay_s: float = 0.4  # pacing of the fixture replay of run events

    def timeout_for(self, agent: str) -> float:
        return self.agent_timeouts_s.get(agent, self.agent_timeout_s)

    def max_age_for(self, adapter: str, default: int | None = None) -> int:
        return self.mirror_max_age_overrides_s.get(adapter, default or self.mirror_max_age_s)

    def model_for(self, task: Literal["memo", "critic", "classify", "analyst"]) -> str:
        specific = {
            "memo": self.llm_model_memo,
            "critic": self.llm_model_critic,
            "classify": self.llm_model_classify,
            "analyst": self.llm_model_analyst,
        }[task]
        return specific or self.llm_model_default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
