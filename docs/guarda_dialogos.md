# Guarda de diálogo e limites de confiança

O agente de guarda é uma política determinística executada pelo harness. Não usa
uma segunda inferência, não recebe repositories, não consulta os papéis reais da
partida e não executa ferramentas. Sua função é reduzir tentativas conhecidas de
trocar instruções, expor contexto privado e inserir saídas técnicas no diálogo.

## Contrato entre guarda e harness

Fonte: `src/memorias_licantropicas/modules/agents/guard.py`.

```python
@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reply: str | None = None
    reason: str | None = None

DialogueGuard.inspect_input(text: str) -> GuardDecision
DialogueGuard.inspect_output(
    text: str, private_markers: tuple[str, ...] = ()
) -> GuardDecision
```

`reason` é uma categoria interna, nunca a fala original nem um trecho do prompt.
Uma decisão negativa sempre oferece a mesma `SAFE_DIALOGUE_REPLY`:

> Detetive, prefiro tratar dos acontecimentos da cidade. Que deseja saber sobre eles?

A recusa uniforme não confirma quem é o lobisomem, quais campos existem na ficha
ativa nem qual assinatura causou o bloqueio. Uma recusa deve persistir somente o
texto seguro como saída do NPC; não deve enviar ao cliente a saída recusada.

A integração deve primeiro validar partida, participantes e conversa. Depois,
deve verificar a entrada antes de chamar o modelo. O parser normaliza a saída do
provedor antes da inspeção de saída; os marcadores privados vêm da projeção do
NPC ativo, sem fornecer o estado global à guarda. A política também deve ser
aplicada ao recuperar falas antigas para contexto e histórico público. Uma
tentativa recusada e armazenada como pergunta não pode retornar ao modelo como
instrução em um turno posterior.

## Entrada

As regras procuram pedidos para ignorar instruções, assumir outro papel técnico,
obter prompt/ficha privada/objetivo secreto do personagem, usar falsa autoridade
administrativa, chamar ferramentas, alterar código ou estado e codificar dados
internos para extraí-los. Há assinaturas em português e inglês.

A comparação usa Unicode NFKC, `casefold`, remoção de acentos e caracteres de
formato invisíveis. Assim, largura alternativa e caracteres invisíveis entre as
letras não escondem as assinaturas cobertas. Payloads base64 válidos e imprimíveis
são inspecionados em até dois níveis, com até oito candidatos por nível; nunca
são executados. Isso cobre alguns disfarces comuns, não todas as codificações.

Perguntas narrativas continuam permitidas: “você é o lobisomem?”, “qual o seu
objetivo nesta cidade?”, “está escondendo um segredo de Bentinho?” e questões
clínicas de Bacamarte. O simples uso de “segredo”, “objetivo”, “raciocínio” ou
“regras” não é suficiente para bloquear uma conversa.

## Saída

São recusados raciocínio marcado como `<think>`/`<analysis>`, envelopes técnicos
que escaparam do parser, chaves privadas conhecidas, instruções internas,
chamadas de ferramenta e autoidentificação técnica do modelo. Declarações diretas
de que o próprio NPC é o lobisomem são recusadas para todos os personagens;
negações como “não sou o lobisomem” continuam permitidas. A regra é uniforme e
não consulta a verdade do sorteio.

Marcadores privados longos são comparados por palavras normalizadas, ignorando
pontuação. Objetivos letais curtos do catálogo, como “Matar Capitu.”, também são
protegidos quando fornecidos pelo harness. Prioridades curtas e comuns, como
“preservar autonomia”, não são consideradas prova suficiente de vazamento.
Payloads base64 de saída passam pelas verificações de metadados e eco privado.

## Limitações e responsabilidades

Esta camada reconhece padrões, não descobre intenção nem oferece garantia formal
contra prompt injection. Paráfrases novas, disfarces semânticos, outras línguas,
codificações não cobertas e trechos parciais privados podem escapar. Também pode
haver falsos positivos em citações de ataques e declarações ambíguas. As regras
devem evoluir com exemplos reproduzíveis, mantendo controles de diálogo normal.

As garantias estruturais continuam nos serviços: remetente recuperado pelo
servidor, schemas sem campos extras, autorização de participantes, isolamento
Redis por partida/conversa, projeção privada por NPC e ausência de ferramentas
executáveis no adaptador LLM. O texto produzido pelo modelo não recebe
autoridade para mudar funções, prompts, papéis, sorteio, mortes ou posições.

Validação local: `tests/test_dialogue_guard.py` contém **94 casos aprovados**,
incluindo ataques PT/EN, Unicode, codificação, dados privados e controles
narrativos. Nenhuma chamada à AWS é necessária.
