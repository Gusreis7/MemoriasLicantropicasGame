"""Assuntos autorais distribuídos por perspectiva; não são provas do crime."""
from uuid import NAMESPACE_URL, uuid5

from src.contracts.social import KnowledgeEntry
from src.modules.knowledge.rules import initial_relationships

# Cada raiz representa um assunto original; retransmissões preservam esta raiz.
TOPICS = (
    ('casamento', ('bentinho','capitu','escobar','virgilia','florenca','rubiao','bacamarte'),
     ('bentinho','capitu'), 'Capitu e Bentinho são casados; o ciúme dele tem provocado discussões.', 'report', 'public', 0),
    ('amizade-capitu-escobar', ('capitu','escobar','bentinho','virgilia'),
     ('capitu','escobar'), 'Capitu e Escobar são amigos e se encontram nos parques e no trabalho. Isso alimenta o ciúme de Bentinho.', 'report', 'public', 0),
    ('suspeita-ciume', ('bentinho',), ('capitu','escobar'),
     'Desconfio de que Capitu e Escobar escondem algo; não tenho prova, mas aquele homem me irrita.', 'interpretation', 'public', 0),
    ('seminario', ('bentinho','escobar','virgilia','bacamarte'), ('bentinho','escobar'),
     'Bentinho e Escobar estudaram juntos no seminário e mantiveram uma ligação antiga.', 'report', 'public', 0),
    ('rumor-afeto', ('virgilia','capitu'), ('escobar','bentinho'),
     'Às vezes me pergunto se a atenção de Escobar a Bentinho é apenas amizade de seminário. É uma impressão minha.', 'interpretation', 'public', 0),
    ('tratamento', ('capitu','bentinho','bacamarte'), ('bentinho','bacamarte'),
     'Bentinho faz acompanhamento com Bacamarte, mas resiste às consultas e à medicação. Não sei confirmar cada dose.', 'report', 'public', 0),
    ('separacao', ('capitu',), ('capitu','bentinho'),
     'Penso em me separar de Bentinho; ainda não contei essa decisão a ele.', 'report', 'private', 65),
    ('afeto-escobar', ('escobar',), ('escobar','bentinho'),
     'O que sinto por Bentinho vai além da amizade, desde nossos dias no seminário.', 'report', 'private', 65),
    ('causa-florenca', ('florenca','virgilia','bacamarte'), ('florenca','bacamarte'),
     'Florença contesta Bacamarte por ter internado seu pai e procura quem a escute.', 'report', 'public', 0),
    ('rubiao-insistente', ('florenca','virgilia','rubiao'), ('florenca','rubiao'),
     'Rubião tenta aproximar-se de Florença, embora ela não corresponda e se incomode com a insistência.', 'report', 'public', 0),
)


def seed_social_state(state, character_ids, now):
    """Migração aditiva e idempotente: não apaga o que uma partida já ouviu."""
    if state.seeded_topics_version >= 3:
        return state
    ids = set(character_ids)
    entries = list(state.knowledge)
    known = {e.id for e in entries}
    for topic, owners, subjects, text, kind, visibility, threshold in TOPICS:
        root = uuid5(NAMESPACE_URL, f'{state.game_id}:author-topic:{topic}')
        for owner in owners:
            if owner not in ids:
                continue
            identifier = uuid5(NAMESPACE_URL, f'{root}:{owner}')
            if identifier in known:
                # Update authored disclosure policy only; retain heard history and old causes.
                entries=[entry.model_copy(update={'visibility':visibility,'disclosure_threshold':threshold})
                         if entry.id==identifier and entry.origin=='authored' else entry for entry in entries]
                continue
            entries.append(KnowledgeEntry(id=identifier, owner_id=owner, root_id=root,
                source_message_id=root, speaker_id=owner, source_span=text, proposition=text,
                subject_ids=tuple(s for s in subjects if s in ids), kind=kind,
                confidence='medium' if kind == 'report' else 'low', stance='believes',
                origin='authored', visibility=visibility, disclosure_threshold=threshold, day=1, created_at=now))
    # Rebase sobre a nova matriz sem apagar os deltas e as causas da partida.
    from src.modules.knowledge.rules import legacy_relationships
    legacy={(r.actor_id,r.target_id):r for r in legacy_relationships(tuple(sorted(ids)))}
    existing={(r.actor_id,r.target_id):r for r in state.relationships}
    relations=[]
    matrix_present=any(r.sentiments for r in state.relationships)
    for base in initial_relationships(tuple(sorted(ids))):
        pair=(base.actor_id,base.target_id); current=existing.pop(pair,None)
        if current is None: relations.append(base); continue
        old=legacy.get(pair)
        values={key:getattr(current,key) for key in ('affinity','trust','resentment','suspicion','loyalty')} if matrix_present else {key:min(100,max(-100 if key in ('affinity','trust') else 0,
                    getattr(base,key)+getattr(current,key)-(getattr(old,key) if old else 0)))
                for key in ('affinity','trust','resentment','suspicion','loyalty')}
        relations.append(current.model_copy(update={**values,'sentiment_label':base.sentiment_label,'sentiments':base.sentiments}))
    relations.extend(existing.values())
    return state.model_copy(update={'knowledge':tuple(entries), 'relationships':tuple(relations),
                                    'seeded_topics_version':3})
