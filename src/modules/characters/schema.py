from typing import Literal

from pydantic import BaseModel, ConfigDict


class CharacterPublic(BaseModel):
    """A apresentação não revela objetivos, consciência do papel ou segredos."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    bio: str
    grammatical_gender: Literal["masculine", "feminine"] = "masculine"
