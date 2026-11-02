"""Verificações locais de presenças e atribuições conhecidas; não é um juiz semântico."""

import re
import unicodedata


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def ground_dialogue_output(content, observations, names):
    if observations is None:
        return content
    text = normalized(content)
    versions = observations.get("suas_versoes_de_interrogatorio", ())
    locations = {"praca_verde": "praca", "cabana_capitu": "cabana", "casa_verde": "casa verde",
                 "cafe_largo": "cafe", "cais_lanternas": "cais"}
    has_presence = re.search(r"\b(?:eu\s+)?(?:estava|estive|passei|encontrei|fui|andava|andei)\b", text)
    own_locations = {locations.get(record.get("local_id")) for record in versions}
    if has_presence and any(place in text and place not in own_locations for place in locations.values()):
        return (versions[-1]["fala"] if versions else
                "Não tenho uma lembrança registrada desse período que sustente uma presença. "
                "Prefiro esclarecer meu álibi no interrogatório a inventar uma certeza.")
    memory = observations.get("memoria_social", {})
    known_sources = {entry.get("quem_falou") for entry in memory.get("memorias_relevantes", ())}
    known_sources.update(entry.get("interlocutor_id") for entry in memory.get("encontros_anteriores", ()) if entry.get("falas"))
    for identifier, name in names.items():
        if identifier in known_sources or identifier == "player":
            continue
        person = re.escape(normalized(name.split()[0]))
        direct_source = (rf"\b{person}\b.{{0,16}}\bme (?:contou|disse|relatou|avisou)\b|"
                         rf"\b(?:ouvi(?: dizer)?[ ,]*(?:de|pela?|da)|soube por|por meio de)\s+(?:senhora?\s+)?{person}\b|"
                         rf"\b(?:me foi (?:contad[ao]|dit[ao]|relatad[ao]) por)\s+{person}\b")
        if re.search(direct_source, text):
            return ("Não recebi esse relato diretamente dessa pessoa. Distingo o que ouvi de Floriano "
                    "do que presenciei; não tenho outra fonte confirmada para acrescentar.")
    return content
