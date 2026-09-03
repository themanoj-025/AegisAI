"""Application configuration using pydantic-settings.

All environment variables are loaded from .env and validated through a single Settings class.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for AegisAI, loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
    )

    # GitHub App credentials
    github_app_id: str = ""
    github_private_key_path: str = "./github-app-private-key.pem"
    github_webhook_secret: str = ""

    # LLM provider configuration
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"

    # Infrastructure
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://user:pass@localhost:5432/aegisai"
    workspace_dir: str = "./workspace"

    # API authentication
    aegis_api_key: str = ""

    # CORS — comma-separated list of allowed origins (AEGIS_CORS_ORIGINS)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Webhook retry queue — when a review job cannot be enqueued, the event is
    # persisted and retried with exponential backoff before dead-lettering.
    webhook_retry_queue: str = "webhook-retry"
    webhook_retry_max_attempts: int = 5
    webhook_retry_backoff: str = "60,300,900,1800"  # seconds between retries

    # Review job execution — transient worker failures are retried by RQ.
    review_job_timeout: int = 1800
    review_job_max_retries: int = 3
    review_job_backoff: str = "60,300,900"  # seconds between retries


settings = Settings()
