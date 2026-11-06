"""Funções sociais puras, limitadas e sem conhecimento do papel de lobisomem."""
from src.contracts.social import Relationship


def clamp(value, lower=0.0, upper=1.0):
    return min(upper, max(lower, float(value)))


def relation_for(relationships, actor, target):
    return next((r for r in relationships if r.actor_id == actor and r.target_id == target),
                Relationship(actor_id=actor, target_id=target))


def closeness(relation):
    """Acesso a confidências; afeto sozinho não equivale a confiança."""
    return clamp(.25 + .35 * relation.trust / 100 + .25 * relation.affinity / 100
                 + .15 * relation.loyalty / 100 - .30 * relation.resentment / 100) * 100


def can_share(entry, relationships, sender, recipient, *, game_id=None):
    if entry.owner_id != sender:
        return False
    if entry.visibility == 'public':
        return True
    if entry.visibility == 'private' and sender != entry.owner_id:
        return False
    if entry.visibility == 'private' and game_id is not None and entry.origin == 'authored':
        from uuid import NAMESPACE_URL, uuid5
        from src.modules.knowledge.seeds import TOPICS
        permitted_roots = {uuid5(NAMESPACE_URL, f'{game_id}:author-topic:{topic}')
                           for topic, owners, _, _, _, visibility, _ in TOPICS
                           if visibility == 'private' and sender in owners}
        if entry.root_id in permitted_roots and can_confide_personal(sender, relation_for(relationships, sender, recipient)):
            return True
    return closeness(relation_for(relationships, sender, recipient)) >= entry.disclosure_threshold


def gossip_weight(source_relation, target_relation, kind='report'):
    """Força subjetiva de um relato; não é veracidade nem cria corroboração."""
    bias = (target_relation.resentment + target_relation.suspicion) / 200
    return clamp(.35 + .25 * source_relation.trust / 100 + .15 * bias
                 - .15 * max(0, target_relation.affinity) / 100
                 - (.15 if kind == 'interpretation' else 0), .05, .8)


def vote_scores(voter_id, suspect_id, relationships, proof_strength, argument_strength):
    """Scores públicos comparáveis; ninguém consulta o papel do acusado ou do eleitor.

    Forças [0,1]. A decisão/maioria e o conjunto de eleitores pertencem à assembleia.
    """
    proof, argument = clamp(proof_strength), clamp(argument_strength)
    suspect = relation_for(relationships, voter_id, suspect_id)
    player = relation_for(relationships, voter_id, 'player')
    credibility = clamp(.65 + .35 * player.trust / 100 - .25 * player.resentment / 100)
    accuse = (.10 + .72 * proof + .18 * argument * credibility
              + .18 * suspect.suspicion / 100 + .12 * suspect.resentment / 100
              - .14 * suspect.affinity / 100 - .12 * suspect.loyalty / 100
              - .08 * suspect.trust / 100)
    backlash = (.03 + .28 * max(0, -player.trust) / 100
                + .24 * player.resentment / 100 + .24 * player.suspicion / 100
                + .12 * max(0, -player.affinity) / 100
                + .20 * (1 - proof) * (1 - argument)
                - .22 * proof - .12 * max(0, player.trust) / 100)
    # O acusado pode defender-se e dirigir a reação contra Floriano, mas não se condena.
    return {suspect_id: 0.0 if voter_id == suspect_id else clamp(accuse),
            'player': clamp(backlash)}


def can_confide_personal(npc_id, relation):
    """Dois ou mais dias de ajuda real abrem algumas confidências; um elogio não."""
    if relation.resentment > 15:
        return False
    if closeness(relation) >= 65:
        return True  # Existing close friends can already receive a confidence.
    if npc_id == 'escobar':
        return relation.trust >= 20 and relation.affinity >= 12 and closeness(relation) >= 35
    return relation.trust >= 10 and relation.affinity >= 6 and closeness(relation) >= 30
