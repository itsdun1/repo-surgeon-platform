"""Application config from environment / .env.local."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[2]  # surgeon-service/app/config.py -> monorepo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(_REPO_ROOT / ".env.local"), ".env.local"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    default_model: str = Field(default="anthropic:claude-opus-4-7", alias="DEFAULT_MODEL")
    fallback_model: str = Field(default="openai:gpt-5.1", alias="FALLBACK_MODEL")

    # GitHub App
    github_app_id: str = Field(default="", alias="GITHUB_APP_ID")
    github_app_private_key_path: str = Field(
        default="./secrets/github-app-private-key.pem", alias="GITHUB_APP_PRIVATE_KEY_PATH"
    )
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    github_webhook_secret_previous: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET_PREVIOUS")

    # Storage / queue
    database_url: str = Field(
        default="postgresql+asyncpg://surgeon:dev@localhost:5432/surgeon",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Paths
    agent_repo_path: str = Field(default="../repo-surgeon", alias="AGENT_REPO_PATH")
    agent_repo_remote: str = Field(default="", alias="AGENT_REPO_REMOTE")
    workspace_root: str = Field(default="/tmp/surgeon-workspace", alias="WORKSPACE_ROOT")
    log_root: str = Field(default="./logs", alias="LOG_ROOT")

    # Safety
    max_cost_usd_per_run: float = Field(default=2.0, alias="MAX_COST_USD_PER_RUN")
    max_duration_s_per_run: int = Field(default=1800, alias="MAX_DURATION_S_PER_RUN")
    max_prs_per_repo_per_day: int = Field(default=5, alias="MAX_PRS_PER_REPO_PER_DAY")

    # Tunnel
    smee_url: str = Field(default="", alias="SMEE_URL")

    @property
    def github_app_private_key(self) -> str:
        raw = self.github_app_private_key_path
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        if not p.exists():
            return ""
        return p.read_text()

    def resolved_agent_repo_path(self) -> Path:
        p = Path(self.agent_repo_path).expanduser()
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        return p


settings = Settings()
