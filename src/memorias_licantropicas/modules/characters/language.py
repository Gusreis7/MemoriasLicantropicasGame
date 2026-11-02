"""Concordância da pessoa; o substantivo 'lobisomem' continua masculino."""

from memorias_licantropicas.contracts.model import CharacterProfile


def participle(profile: CharacterProfile | None, masculine: str, feminine: str) -> str:
    return feminine if profile and profile.grammatical_gender == "feminine" else masculine
