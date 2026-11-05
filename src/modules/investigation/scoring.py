"""Peso probatório por espécie, exame e fontes; não consulta culpado ou verdade privada."""
from dataclasses import dataclass

from src.contracts.errors import ConflictError, NotFoundError
from src.modules.investigation.catalog import ITEMS_BY_ID

MATERIAL_WEIGHTS = {"common": .25, "singular": 1., "unique": 3.}
COMMON_TOTAL_CAP = .5
SINGULAR_TOTAL_CAP = 2.
CUSTODY_THRESHOLD = 5.


@dataclass(frozen=True)
class DossierAssessment:
    material_points: float
    source_bonus: float
    contradiction_bonus: float
    total: float
    linked_item_ids: frozenset[str]
    examined_exclusive_ids: frozenset[str]
    independent_witnesses: frozenset[str]
    alibi_conflict: bool
    accepted: bool
    corroborated_personal_ids: frozenset[str] = frozenset()
    custody_route: str | None = None


def public_alibi_conflict(state, suspect_id):
    """Somente declarações já no caderno; nunca lê o registro privado de atividades."""
    return any(
        own.npc_id == suspect_id and own.location_id is not None
        and witness.npc_id != suspect_id and witness.day == own.day and witness.period == own.period
        and any(observation.npc_id == suspect_id and observation.source == 'observed'
                and observation.location_id != own.location_id for observation in witness.observations)
        for own in state.interrogations for witness in state.interrogations
    )


def assess_dossier(state, suspect_id, evidence_ids, testimony_ids, report_ids=()):
    # Importação local evita que as regras de busca e de avaliação formem um ciclo.
    from src.modules.investigation.rules import find_evidence
    selected = tuple(find_evidence(state, identifier) for identifier in dict.fromkeys(evidence_ids))
    selected_types = {evidence.item_id for evidence in selected}
    by_id = {record.id: record for record in state.testimonies}
    if any(identifier not in by_id for identifier in testimony_ids):
        raise NotFoundError("Depoimento não encontrado nesta partida.")
    statements = tuple(by_id[identifier] for identifier in dict.fromkeys(testimony_ids))
    items_by_statement = {record.id: find_evidence(state, record.evidence_id).item_id for record in statements}
    if any(items_by_statement[record.id] not in selected_types for record in statements):
        raise ConflictError("Um depoimento precisa acompanhar seu vestígio na acusação.")
    linked = tuple(record for record in statements
                   if record.recognition == 'recognizes' and record.claimed_owner_id == suspect_id)
    item_ids = frozenset(items_by_statement[record.id] for record in linked)
    witnesses = frozenset(record.witness_id for record in linked if record.witness_id != suspect_id)
    common = sum(MATERIAL_WEIGHTS['common'] for item in item_ids if ITEMS_BY_ID[item].kind == 'common')
    singular = sum(MATERIAL_WEIGHTS['singular'] for item in item_ids if ITEMS_BY_ID[item].kind == 'singular')
    unique = sum(MATERIAL_WEIGHTS['unique'] for item in item_ids if ITEMS_BY_ID[item].kind == 'unique')
    material = min(COMMON_TOTAL_CAP, common) + min(SINGULAR_TOTAL_CAP, singular) + unique
    examined = frozenset(e.item_id for crime in state.crimes for e in crime.evidence
        if e.collected and e.item_id in selected_types and e.item_id in item_ids and ITEMS_BY_ID[e.item_id].kind == 'unique'
        and getattr(e, 'examined', False) and getattr(e, 'crime_link_verified', False))
    source_bonus = .5 * min(2, len(witnesses))
    conflict = public_alibi_conflict(state, suspect_id)
    contradiction_bonus = .75 if conflict and witnesses else 0.
    from src.modules.characters.catalog import CHARACTERS
    from src.textutils import normalize, word_tokens, has_any_phrase
    name = next((person.name for person in CHARACTERS if person.id == suspect_id), suspect_id)
    name_tokens = set(word_tokens(normalize(name)))
    available = {event.get('outgoing_id'): event for event in state.dialogue_events
                 if event.get('narrative_authorized') and event.get('useful')
                 and event.get('assessment', {}).get('kind') in ('alibi', 'suspicion')}
    selected_reports = []
    for identifier in dict.fromkeys(report_ids):
        event = available.get(str(identifier))
        if event is None:
            raise NotFoundError('Relato útil não encontrado nesta partida.')
        selected_reports.append(event)
    accusing_sources = set()
    unconfirmed = False
    for event in selected_reports:
        tokens = set(word_tokens(normalize(event.get('outgoing', ''))))
        kind = event['assessment']['kind']
        if kind == 'suspicion' and event['npc_id'] != suspect_id and name_tokens & tokens:
            accusing_sources.add(event['npc_id'])
        mentions_other = any(person.id != suspect_id and has_any_phrase(normalize(event.get('outgoing', '')),
                             (f"com {normalize(person.name.split()[0])}", f"cuidando de {normalize(person.name.split()[0])}",
                              f"companhia de {normalize(person.name.split()[0])}"))
                             for person in CHARACTERS)
        if kind == 'alibi' and event['npc_id'] == suspect_id and not mentions_other and (tokens & {'sozinho', 'sozinha', 'ninguem', 'desacompanhado', 'desacompanhada'} or has_any_phrase(normalize(event.get('outgoing', '')), ('sem companhia', 'nao tive companhia', 'sem testemunhas', 'nao tenho quem confirme', 'nao me lembro se alguem', 'nao sei se alguem me viu', 'nao me lembro exatamente da hora ou se alguem me viu'))):
            unconfirmed = True
    report_bonus = min(3., 2. * len(accusing_sources)) + (2. if unconfirmed else 0.)
    total = material + source_bonus + contradiction_bonus + report_bonus
    corroborated = len(witnesses) >= 2 or (bool(witnesses) and conflict)
    # O reconhecimento de duas marcas distintas por duas fontes por peça já
    # permite custódia: não exigir um clique de exame redundante neste caminho.
    personal_sources = {item: frozenset(record.witness_id for record in linked
        if items_by_statement[record.id] == item and record.witness_id != suspect_id)
        for item in item_ids if ITEMS_BY_ID[item].kind == 'unique'}
    personal = frozenset(item for item, sources in personal_sources.items() if len(sources) >= 2)
    examined_route = bool(len(item_ids) >= 2 and examined and corroborated and total >= CUSTODY_THRESHOLD)
    witness_route = len(personal) >= 2 and total >= CUSTODY_THRESHOLD
    report_route = bool(accusing_sources and unconfirmed and (item_ids or len(accusing_sources) >= 2))
    accepted = examined_route or witness_route or report_route
    route = 'examined_trace' if examined_route else 'corroborated_personal_marks' if witness_route else 'witness_reports' if report_route else None
    return DossierAssessment(material, source_bonus, contradiction_bonus, total, item_ids,
                             examined, witnesses, conflict, accepted, personal, route)


def dossier_strength(assessment):
    """Força do dossiê na assembleia, sem bônus por quantidade de cópias ou IDs anexados."""
    if assessment.accepted:
        return min(1., .78 + .08 * min(len(assessment.independent_witnesses), 2))
    if assessment.examined_exclusive_ids:
        return min(.65, assessment.total / CUSTODY_THRESHOLD * .65)
    # Indícios genéricos podem motivar suspeita, mas não uma certeza coletiva.
    return min(.35, assessment.total / CUSTODY_THRESHOLD * .5)
