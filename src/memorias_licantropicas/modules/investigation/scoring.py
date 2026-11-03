"""Peso probatório por espécie, exame e fontes; não consulta culpado ou verdade privada."""
from dataclasses import dataclass

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError
from memorias_licantropicas.modules.investigation.catalog import ITEMS_BY_ID

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


def public_alibi_conflict(state, suspect_id):
    """Somente declarações já no caderno; nunca lê o registro privado de atividades."""
    return any(
        own.npc_id == suspect_id and own.location_id is not None
        and witness.npc_id != suspect_id and witness.day == own.day and witness.period == own.period
        and any(observation.npc_id == suspect_id and observation.source == 'observed'
                and observation.location_id != own.location_id for observation in witness.observations)
        for own in state.interrogations for witness in state.interrogations
    )


def assess_dossier(state, suspect_id, evidence_ids, testimony_ids):
    # Importação local evita que as regras de busca e de avaliação formem um ciclo.
    from memorias_licantropicas.modules.investigation.rules import find_evidence
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
    total = material + source_bonus + contradiction_bonus
    corroborated = len(witnesses) >= 2 or (bool(witnesses) and conflict)
    accepted = bool(len(item_ids) >= 2 and examined and corroborated and total >= CUSTODY_THRESHOLD)
    return DossierAssessment(material, source_bonus, contradiction_bonus, total, item_ids,
                             examined, witnesses, conflict, accepted)


def dossier_strength(assessment):
    """Força do dossiê na assembleia, sem bônus por quantidade de cópias ou IDs anexados."""
    if assessment.accepted:
        return min(1., .78 + .08 * min(len(assessment.independent_witnesses), 2))
    if assessment.examined_exclusive_ids:
        return min(.65, assessment.total / CUSTODY_THRESHOLD * .65)
    # Indícios genéricos podem motivar suspeita, mas não uma certeza coletiva.
    return min(.35, assessment.total / CUSTODY_THRESHOLD * .5)
