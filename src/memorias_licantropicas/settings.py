"""Configuração local/ambiente; nenhuma credencial é necessária no startup."""

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
    bedrock_api_key: SecretStr | None = Field(
        default=None, validation_alias="AWS_BEARER_TOKEN_BEDROCK",
    )
    bedrock_base_url: str | None = None
    bedrock_model: str = Field(default="qwen.qwen3-32b", min_length=1)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_max_tokens: int = Field(default=512, ge=1, le=2048)
    llm_history_limit: int = Field(default=20, ge=1, le=100)

    @field_validator("bedrock_base_url", mode="before")
    @classmethod
    def empty_url_is_default(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @property
    def mantle_base_url(self) -> str:
        return self.bedrock_base_url or f"https://bedrock-mantle.{self.aws_region}.api.aws/v1"
