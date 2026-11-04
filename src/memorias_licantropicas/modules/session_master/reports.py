"""Classificar utilidade não certifica verdade: fofoca com fonte também pode ajudar."""
import re
from memorias_licantropicas.modules.agents.support import words, normalized, NAMES


def useful_report(content, observations, *, kind='conversation', quote='', suggested=False):
 if not observations or not content.strip():return False
 text=normalized(content)
 if re.fullmatch(r'(?:ola|oi|bom dia|boa tarde|boa noite|obrigad[oa])[.! ,]*',text):return False
 if re.search(r'\b(?:nao sei|nao reconheco|nada a declarar)\b',text) and not re.search(r'\b(?:vi|ouvi|pergunte|procure|converse)\b',text):return False
 from memorias_licantropicas.modules.session_master.service import own_assertion_clauses
 plot=observations.get('seu_conflito_privado') or {}
 if plot.get('estado')=='succeeded' and any(
     re.search(r'\b(?:matei|assassinei)\b',clause) and normalized(plot.get('alvo','')) in clause
     for clause in own_assertion_clauses(content)):
  return True
 actual=words(content)-{normalized(n) for n in NAMES.values()}
 for support in observations.get('apoios_de_conversa',()):
  expected=words(support.get('statement',''))-{normalized(n) for n in NAMES.values()}
  if len(actual & expected)>=min(4,max(2,len(expected)//3)):
   return True
 # O mestre pode selecionar uma fala própria de álibi ou admissão literal, nunca texto do jogador.
 return bool(suggested and quote and quote in content and kind in ('alibi','admission')
             and re.search(r'\b(?:estava|estive|vi|matei|ataquei|sou o lobisomem)\b',text))
