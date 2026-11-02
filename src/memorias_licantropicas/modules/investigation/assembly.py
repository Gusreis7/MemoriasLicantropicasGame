"""Votação limitada, com motivos públicos e sem onisciência civil."""
from memorias_licantropicas.contracts.investigation import AssemblyRecord, AssemblyVote
from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError
from memorias_licantropicas.modules.investigation.rules import evaluate_accusation

CAUTION = {"rubiao": 4, "virgilia": 4, "florenca": 4, "bentinho": 5,
           "escobar": 5, "capitu": 5, "bacamarte": 6}


def convene(state, game, suspect_id, evidence_ids, testimony_ids, now):
    if state.assembly is not None:
        raise ConflictError("A assembleia já foi convocada nesta partida.")
    eligible = [m for m in game.characters if m.alive and m.character_id not in state.expelled_npc_ids
                and m.character_id != state.detained_npc_id]
    if suspect_id not in {m.character_id for m in eligible}:
        raise NotFoundError("Escolha um suspeito vivo e livre.")
    assessment = evaluate_accusation(state, suspect_id, evidence_ids, testimony_ids, now)
    statements = [t for t in state.testimonies if t.id in testimony_ids
                  and t.recognition == "recognizes" and t.claimed_owner_id == suspect_id]
    witnesses = {t.witness_id for t in statements}
    votes = [AssemblyVote(voter_id="player", expel=True, reason="Floriano apresentou o pedido de expulsão.")]
    for member in eligible:
        actor = member.character_id
        # Só o próprio lobo conhece sua identidade. Civis avaliam o mesmo dossiê público.
        agrees = (assessment.accepted and len(witnesses) >= (2 if CAUTION.get(actor, 6) >= 5 else 1)
                  and actor != suspect_id)
        if member.role == "werewolf":
            agrees = actor != suspect_id and assessment.accepted
        votes.append(AssemblyVote(voter_id=actor, expel=agrees,
            reason=("Os vestígios e as fontes apresentadas sustentam minha decisão." if agrees else
                    "Não considero o conjunto suficiente para autorizar esta expulsão.")))
    required = len(votes) // 2 + 1
    expelled = sum(v.expel for v in votes) >= required
    wolf = next(m.character_id for m in game.characters if m.role == "werewolf")
    return AssemblyRecord(evidence_ids=evidence_ids, testimony_ids=testimony_ids, suspect_id=suspect_id, day=state.day, votes=tuple(votes), required_votes=required,
        expelled=expelled, outcome=("werewolf" if suspect_id == wolf else "innocent") if expelled else "no_majority",
        created_at=now)
