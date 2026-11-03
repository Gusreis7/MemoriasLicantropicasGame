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


def discoveries_in_reply(npc_id,content,allowed_ids):
 """Os IDs permitidos vêm do contexto privado; a pergunta do jogador nunca é usada."""
 text=normalize(content)
 # A named secret in a question, citation, denial or hypothetical is not a discovery.
 clauses=[]
 for raw in re.split(r'(?<=[.!?;])|\n',re.sub(r'[«“"].*?[»”"]','',text,flags=re.S)):
  if raw.strip().endswith('?'):continue
  if re.search(r'\b(nao|nunca|jamais|talvez|se|dizem que|ouvi dizer)\b',raw):continue
  clauses.append(raw)
 plain=' '.join(clauses)
 found=[]
 allowed=set(allowed_ids)
 def has(*groups):return all(any(re.search(pattern,plain) for pattern in group) for group in groups)
 checks={
 'marriage_triangle':has(('capitu',),('bentinho',),('escobar',),('casad|casamento|marido',),('amig|amizade',)),
 'seminary_bond':has(('bentinho',),('escobar',),('seminario',),('estud|amig|ligacao|juntos',)),
 'treatment_bentinho':has(('bentinho',),('bacamarte',),('tratamento|medicacao|remedio|consult',),('resist|evita|falta|recusa|nao toma',)),
 'florenca_father':has(('florenca|meu pai',),('pai',),('intern|casa verde',),('bacamarte',)),
 'capitu_separation':npc_id=='capitu' and has(('quero|desejo|penso|pretendo|decidi|vou',),('separ|deixar meu marido|deixar bentinho',)),
 'escobar_affection':npc_id=='escobar' and has(('bentinho',),('amo|apaixon|sinto por|meu amor|alem da amizade|mais que amizade',)),
 }
 for identifier,accepted in checks.items():
  if identifier in allowed and accepted:found.append(identifier)
 return tuple(found)
