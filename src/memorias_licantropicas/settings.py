"""Configuração local/ambiente; nenhuma credencial é necessária no startup."""

from decimal import Decimal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
        populate_by_name=True,
    )

    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    redis_prefix: str = Field(default="ml:v1", min_length=1)
    aws_region: str = Field(default="us-east-1", min_length=1)
    aws_profile: str | None = None
    bedrock_api_key: SecretStr | None = Field(
        default=None, validation_alias="AWS_BEARER_TOKEN_BEDROCK",
    )
    bedrock_base_url: str | None = None
    bedrock_model: str = Field(default="qwen.qwen3-32b", min_length=1)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_max_tokens: int = Field(default=512, ge=1, le=2048)
    llm_history_limit: int = Field(default=20, ge=1, le=100)
    llm_pricing_model: str = "qwen.qwen3-32b"
    llm_pricing_region: str = "us-east-1"
    llm_input_usd_per_million: Decimal | None = Field(default=Decimal("0.15"), ge=0)
    llm_output_usd_per_million: Decimal | None = Field(default=Decimal("0.60"), ge=0)
    llm_pricing_source: str = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json"
    llm_pricing_checked_at: str = "2026-11-01"
    social_enabled: bool = True
    social_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    admin_session_seconds: int = Field(default=28800, ge=60, le=86400)
    admin_cookie_secure: bool = False
    admin_allowed_origins: str = "http://localhost:7078,http://127.0.0.1:7078"

    @field_validator("bedrock_base_url", mode="before")
    @classmethod
    def empty_url_is_default(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @property
    def mantle_base_url(self) -> str:
        return self.bedrock_base_url or f"https://bedrock-mantle.{self.aws_region}.api.aws/v1"
