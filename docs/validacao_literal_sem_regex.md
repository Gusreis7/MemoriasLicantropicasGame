# Validação textual sem expressões regulares

A aplicação não usa uma linguagem alternativa de padrões. `textutils.py` oferece
apenas operações literais: normalização Unicode, palavras, sequência de palavras,
separação por pontuação e remoção de discurso citado por delimitadores explícitos.
Não há compilador, metacaracteres, operadores de regex ou busca de JSON em texto.

As regras determinísticas tratam âncoras verificáveis:

- Campos internos, marcadores de autoridade e pedidos de acesso/execução usam
  vocabulário explícito. Base64 é decodificado com limites, nunca executado.
- Uma citação, pergunta, negação ou hipótese não vira admissão própria. Uma negação
  anterior não oculta uma revelação direta posterior na mesma frase ou linha.
- O parecer tipado do mestre precisa apontar um trecho literal e uma afirmação
  própria antes de autorizar uma confissão. O motor ainda verifica papel, vítima,
  entrega, autoria e resultado; o modelo não decide esses efeitos.
- Presença e fonte exigem declarações próprias explícitas e contexto autorizado.
  Descrever onde outra pessoa estava não afirma a presença do falante. Uma frase
  rejeitada não é reescrita por uma regra local.
- Relações e conquistas continuam dependendo de origem/autorização e IDs canônicos.
  Primeira pessoa é resolvida pelo autor registrado, sem trocar o emissor do relato.

Essas verificações não pretendem equivalência semântica com português livre nem
prova de intenção maliciosa. São controles conservadores de casos conhecidos; o
parecer do mestre e a projeção privada continuam necessários. A retirada de regex
não autoriza diminuir a cobertura para apenas conseguir passar nos testes.

A suíte cobre ataques Unicode, vazamento de prompts, payloads codificados,
confissões reais, negativas, perguntas, citações, hipóteses, fontes privadas,
conquistas e consistência das sessões. Testes adicionais verificam contraste após
negação e impedem que nomes parcialmente parecidos ativem marcadores privados.
