"""Matriz autoral direcionada: ambivalência não é reduzida a uma média de afeto."""
from src.contracts.social import Relationship

IDS = ('bentinho','capitu','escobar','rubiao','florenca','virgilia','bacamarte','bras_cubas')
# A ordem das colunas é IDS; a diagonal descreve a relação consigo mesmo.
MATRIX = {
 'bentinho': ('autodecepção','amor, ódio e ciúme','ódio e ciúme','apatia','apatia','amizade antiga','desconfiança','era seu cliente'),
 'capitu': ('ódio e amor','amor-próprio forte','amizade','ódio','simpatia','amizade','relação de cliente','desprezo'),
 'escobar': ('amor','amizade','medo dos próprios sentimentos','apatia','apatia','amizade','apatia','desprezo'),
 'rubiao': ('admiração','apatia','respeito','ingenuidade','amor e paixão','desprezo','apatia e medo','apatia'),
 'florenca': ('apatia','simpatia','apatia','ódio','força interna','amizade','apatia','desprezo'),
 'virgilia': ('desprezo','amizade','amizade','ódio','amizade','apatia','apatia','amor avassalador'),
 'bacamarte': ('fascínio','apatia','curiosidade','apatia','apatia','apatia','dúvidas sobre a própria mente','apatia e desprezo'),
 'bras_cubas': ('apatia','desprezo','desprezo','desprezo','desprezo','amor','apatia','narcisismo'),
}
# Intensidades independentes [0,100]; confiança e lealdade não se confundem com paixão.
AFFECTS = {
 'autodecepção': {'autodecepção':75}, 'amor, ódio e ciúme': {'amor':85,'ódio':65,'ciúme':90},
 'ódio e ciúme': {'ódio':80,'ciúme':85}, 'apatia': {'apatia':80},
 'amizade antiga': {'amizade':70}, 'desconfiança': {'desconfiança':75},
 'era seu cliente': {'vínculo profissional':65}, 'ódio e amor': {'ódio':75,'amor':65},
 'amor-próprio forte': {'amor-próprio':90}, 'amizade': {'amizade':65}, 'ódio': {'ódio':80},
 'simpatia': {'simpatia':45}, 'relação de cliente': {'vínculo profissional':60},
 'desprezo': {'desprezo':75}, 'amor': {'amor':85},
 'medo dos próprios sentimentos': {'medo':80,'autodúvida':65}, 'admiração': {'admiração':70},
 'respeito': {'respeito':60}, 'ingenuidade': {'ingenuidade':80},
 'amor e paixão': {'amor':85,'paixão':90}, 'apatia e medo': {'apatia':65,'medo':65},
 'força interna': {'determinação':85}, 'amor avassalador': {'amor':100,'paixão':100},
 'fascínio': {'fascínio':85}, 'curiosidade': {'curiosidade':65},
 'dúvidas sobre a própria mente': {'autodúvida':85},
 'apatia e desprezo': {'apatia':65,'desprezo':60}, 'narcisismo': {'narcisismo':90},
}

def affect_relationship(actor, target):
 label=MATRIX[actor][IDS.index(target)]
 affect=AFFECTS[label].copy()
 love=affect.get('amor',0); hate=affect.get('ódio',0); friend=affect.get('amizade',0)
 affinity=round(.75*love+.8*friend+.5*affect.get('simpatia',0)+.5*affect.get('admiração',0)-.8*hate-.6*affect.get('desprezo',0))
 trust=round(.55*friend+.35*affect.get('respeito',0)-.6*affect.get('desconfiança',0)-.35*hate-.25*affect.get('ciúme',0))
 return Relationship(actor_id=actor,target_id=target,sentiment_label=label,sentiments=affect,
  affinity=affinity,trust=trust,resentment=round(.65*hate+.4*affect.get('desprezo',0)),
  suspicion=round(.6*affect.get('ciúme',0)+.5*affect.get('desconfiança',0)),
  loyalty=round(.7*love+.6*friend))

def initial_affects(character_ids):
 ids=tuple(dict.fromkeys((*character_ids,'bras_cubas')))
 return tuple(affect_relationship(actor,target) if actor in MATRIX and target in IDS else Relationship(actor_id=actor,target_id=target,affinity=-5,trust=-25,resentment=5) if (actor,target)==('bacamarte','player') else Relationship(actor_id=actor,target_id=target)
              for actor in ids for target in (*ids,'player'))

def private_affect_context(state,npc_id,authorized_secrets=()):
 """Somente sentimentos do ator; o jogador não recebe a matriz nem segredos de outros."""
 return [{'por':r.target_id,'sentimento':r.sentiment_label,'intensidades':r.sentiments,
          'afinidade':r.affinity,'confianca':r.trust,'ressentimento':r.resentment,
          'regra':('amor é privado: pode motivar suas escolhas, mas só admitir quando autorizado'
                   if (npc_id,r.target_id)==('escobar','bentinho') and not authorized_secrets else
                   'sentimento é sua perspectiva, não prova de culpa')}
         for r in state.relationships if r.actor_id==npc_id]


def relational_impulses(state, npc_id, names):
 """Traduz afetos privados em iniciativas de fala, sem criar fatos do caso."""
 relations = [r for r in state.relationships if r.actor_id == npc_id and r.target_id not in (npc_id, 'player', 'bras_cubas')]
 relations.sort(key=lambda r: (max(r.suspicion, r.resentment), -r.trust, -r.affinity), reverse=True)
 impulses = []
 for relation in relations:
  hostility = max(relation.suspicion, relation.resentment, -relation.trust, -relation.affinity)
  if hostility >= 25:
   impulses.append({
    'alvo_id': relation.target_id,
    'alvo': names.get(relation.target_id, relation.target_id),
    'tipo': 'suspeitar_e_acusar',
    'motivo_emocional': relation.sentiment_label,
    'orientacao': (
     'Pode apontar esta pessoa espontaneamente, interpretar relatos ou objetos contra ela e pedir que Floriano a investigue. '
     'Declare ciúme, antipatia, desconfiança ou ressentimento como motivo pessoal; use talvez, desconfio ou acredito. '
     'Não alegue ter visto um crime nem invente a origem de um objeto.'
    ),
   })
  elif relation.loyalty >= 40 or relation.affinity >= 35:
   impulses.append({
    'alvo_id': relation.target_id,
    'alvo': names.get(relation.target_id, relation.target_id),
    'tipo': 'defender_e_confidenciar',
    'orientacao': (
     'Tende a defender esta pessoa, relativizar acusações contra ela e compartilhar rumores úteis que possam protegê-la, '
     'sem inventar fatos ou revelar intimidades não autorizadas.'
    ),
   })
  if len(impulses) == 4:
   break
 return impulses
