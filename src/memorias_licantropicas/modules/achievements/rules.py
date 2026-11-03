"""Conquistas de informação efetivamente ouvida, com causa e IDs estáveis."""
import re
import unicodedata
from memorias_licantropicas.contracts.investigation import Achievement

DEFINITIONS={
 'marriage_triangle':('Três versões de um casamento','Descobriu o casamento de Capitu e Bentinho e a amizade de Capitu com Escobar.'),
 'seminary_bond':('Amigos do seminário','Ouviu a história da ligação de Bentinho e Escobar no seminário.'),
 'treatment_bentinho':('Consultas e resistências','Descobriu o acompanhamento de Bentinho por Bacamarte e sua resistência ao tratamento.'),
 'florenca_father':('A causa de Florença','Soube da internação do pai de Florença e de sua oposição a Bacamarte.'),
 'capitu_separation':('Uma confidência de Capitu','Capitu lhe confiou o desejo de separar-se de Bentinho.'),
 'escobar_affection':('Além da amizade','Escobar lhe confiou seus sentimentos por Bentinho.'),
 'personal_trace':('Uma marca pessoal','Examinou um vestígio pessoal e identificou sua marca distintiva.'),
}
TOPIC_DISCOVERIES={
 'casamento':'marriage_triangle','amizade-capitu-escobar':'marriage_triangle','seminario':'seminary_bond',
 'tratamento':'treatment_bentinho','causa-florenca':'florenca_father','separacao':'capitu_separation','afeto-escobar':'escobar_affection',
}


def normalize(text):
 return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def award(state,achievement_id,now,*,source_message_id=None,source_npc_id=None):
 if achievement_id not in DEFINITIONS or any(a.id==achievement_id for a in state.achievements):return state
 title,description=DEFINITIONS[achievement_id]
 record=Achievement(id=achievement_id,title=title,description=description,unlocked_at=now,
  source_message_id=source_message_id,source_npc_id=source_npc_id)
 return state.model_copy(update={'achievements':(*state.achievements,record)})


def _assertion_clauses(content):
 text=normalize(content)
 clauses=[]
 for raw in re.split(r'(?<=[.!?;])|\n',re.sub(r'[«“"].*?[»”"]','',text,flags=re.S)):
  if raw.strip().endswith('?'):continue
  # Refusing the medication affirms resistance; negating the treatment itself does not.
  raw=re.sub(r'\bnao toma\b', 'resiste a tomar', raw)
  if re.search(r'\b(nao|nunca|jamais|talvez|se|dizem que|ouvi dizer)\b',raw):continue
  clauses.append(raw)
 return clauses


def discovery_assertions(npc_id,content):
 """Resolve first person per source before joining fragments from different speakers."""
 names={'bentinho':'bentinho','escobar':'escobar','capitu':'capitu','florenca':'florenca',
        'rubiao':'rubiao','virgilia':'virgilia','bacamarte':'bacamarte'}
 name=names.get(npc_id)
 clauses=_assertion_clauses(content)
 if name:
  clauses=[re.sub(r'\beu\b',name,re.sub(r'\bmeu pai\b',f'pai de {name}',clause)) for clause in clauses]
 return ' '.join(clauses)


def discoveries_in_reply(npc_id,content,allowed_ids):
 """Os IDs permitidos vêm do contexto privado; a pergunta do jogador nunca é usada."""
 plain=discovery_assertions(npc_id,content)
 original=' '.join(_assertion_clauses(content))
 found=[]
 allowed=set(allowed_ids)
 def has(*groups):return all(any(re.search(pattern,plain) for pattern in group) for group in groups)
 def own_has(*groups):return all(any(re.search(pattern,original) for pattern in group) for group in groups)
 checks={
 'marriage_triangle':has(('capitu',),('bentinho',),('escobar',),('casad|casamento|marido',),('amig|amizade',)),
 'seminary_bond':has(('bentinho',),('escobar',),('seminario',),('estud|amig|ligacao|juntos',)),
 'treatment_bentinho':has(('bentinho',),('bacamarte',),('tratamento|medicacao|remedio|consult',),('resist|evita|falta|recusa|nao toma',)),
 'florenca_father':has(('florenca',),('pai',),('intern|casa verde',),('bacamarte',)),
 'capitu_separation':npc_id=='capitu' and own_has(('quero|desejo|penso|pretendo|decidi|vou',),('separ|deixar meu marido|deixar bentinho',)),
 'escobar_affection':npc_id=='escobar' and own_has(('bentinho',),('amo|apaixon|sinto por|meu amor|alem da amizade|mais que amizade',)),
 }
 for identifier,accepted in checks.items():
  if identifier in allowed and accepted:found.append(identifier)
 return tuple(found)
