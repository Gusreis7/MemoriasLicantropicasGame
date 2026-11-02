"""Aceitar JSON puro ou um único bloco JSON, mantendo validação estrita."""

import json
import re


def parse_json_object(text: str) -> dict:
    content = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        content = fenced[1].strip()

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Campo JSON duplicado.")
            result[key] = value
        return result

    value = json.loads(content, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("A saída estruturada exige objeto JSON.")
    return value
