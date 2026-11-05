"""Contrato público de fala nova. Identidade e efeitos pertencem ao servidor."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NpcSpeech(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    fala: str = Field(min_length=1, max_length=8000)

    @field_validator("fala")
    @classmethod
    def nonblank_speech(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A fala precisa conter texto.")
        return value
