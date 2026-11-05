"""Operações literais de texto, sem linguagem de padrões ou inferência semântica."""

import unicodedata


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
        and unicodedata.category(character) != "Cf"
    )


def word_tokens(value: str) -> tuple[str, ...]:
    """Palavras Unicode; pontuação separa tokens e identificadores mantêm underscore."""
    characters = (
        character if character.isalnum() or character == "_" else " "
        for character in normalize(value)
    )
    return tuple("".join(characters).split())


def has_phrase(value: str, phrase: str) -> bool:
    """Busca somente uma sequência literal de palavras, sem operadores/padrões."""
    text, expected = word_tokens(value), word_tokens(phrase)
    return bool(expected) and any(
        text[index : index + len(expected)] == expected
        for index in range(len(text) - len(expected) + 1)
    )


def has_any_phrase(value: str, phrases) -> bool:
    return any(has_phrase(value, phrase) for phrase in phrases)


def without_quotes(value: str) -> str:
    """Exclui discurso citado; aspas sem fechamento também não viram afirmação própria."""
    pairs = {"«": "»", "“": "”", "‘": "’", '"': '"'}
    closing = None
    result = []
    for character in value:
        if closing is not None:
            if character == closing:
                closing = None
                result.append(" ")
        elif character in pairs:
            closing = pairs[character]
        else:
            result.append(character)
    return "".join(result)


def clauses(value: str) -> tuple[str, ...]:
    """Separa pontuação de sentença preservando interrogações e texto literal."""
    result, current = [], []
    for character in value:
        current.append(character)
        if character in ".!?;\n":
            phrase = "".join(current).strip()
            if phrase:
                result.append(phrase)
            current = []
    tail = "".join(current).strip()
    if tail:
        result.append(tail)
    return tuple(result)


def has_word_start(value: str, beginnings) -> bool:
    return any(word.startswith(tuple(beginnings)) for word in word_tokens(value))
