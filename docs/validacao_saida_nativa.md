# Validação da correção nativa — 5 de novembro de 2026

Implementação validada: `dd55ebb`, com transporte/ChatModel incorporados de
`2e5355b` e validadores literais de `772489c`. A documentação foi integrada depois.
Os módulos estão diretamente em `src/`; entrypoint `src.main:app`.

## O que foi exercitado

- **852 testes e sete subtestes passaram com Redis real**, em namespaces isolados.
  Incluem requisição HTTP simulada com `tools`, nomes e argumentos inválidos,
  `with_structured_output`, `PydanticToolsParser`, schema estrito, timeout,
  cancelamento, limite de tentativas, isolamento de sessões e persistência.
- **Seis fluxos Playwright passaram no Brave**: exploração, diálogo, retomada,
  mudança de dia, projeção de fala e texto hostil no histórico.
- **Imagem Docker construída e stack de teste saudável** em 17077/17078. Brave
  confirmou bloqueio de script inline pela CSP, admin público indisponível e API
  privada exigindo autenticação/origem permitida. O entrypoint novo foi executado.
- Wheel construído com `src/main.py` e `src/infrastructure/llm/structured.py`;
  não contém o antigo pacote intermediário. `uv lock --check`, `actionlint` e
  `git diff --check` passaram.
- Testes arquiteturais impedem imports de `re`/`regex` no aplicativo, retorno ao
  namespace antigo e restauração do parser textual no gerador.

Os testes de protocolo executam o Runnable e os grafos reais, substituindo apenas
o transporte/inferência. Respostas contendo JSON textual sem ferramenta são
rejeitadas. Marcadores internos em uma fala nativa válida também são bloqueados.
A limpeza posterior removeu também o leitor de histórico antigo e os caminhos
de migração; consulte [a manutenção](limpeza_reinicio.md). Códigos arbitrários de exceção não entram na telemetria de consumo.

## Experimento histórico offline, retirado do runner atual

A execução abaixo utilizou um provedor simulado e não constitui medição de
comportamento de LLM real. Seu runner e relatório gerado foram removidos do
checkout; podem ser consultados no histórico Git anterior à implementação das
[partidas reais com Floriano agente](simulacao_partidas_refatoracao.md).
O Redis era temporário; o runner apagou somente o prefixo exclusivo da execução.

| Indicador | Resultado |
| --- | ---: |
| Partidas encerradas pelo motor | 10/10 |
| Vitórias / derrotas | 8 / 2 |
| Chamadas ao provedor simulado | 761 |
| Respostas de fallback técnico | 26 |
| Erros de autenticação deliberadamente injetados | 40 |
| Chamadas reais AWS / custo AWS real | 0 / US$ 0 |

As sete primeiras partidas não tinham falha injetada. A oitava recebeu argumentos
de ferramenta inválidos uma vez e recuperou na segunda tentativa. A nona recebeu
argumentos sempre inválidos, persistiu 26 fallbacks identificados e continuou pelo
motor. A décima recusou autenticação em 40 tentativas de diálogo, sem fabricar
uma resposta de persona. Isso é contagem de tentativas distintas, não retry de
autenticação dentro de uma chamada. As duas políticas passivas perderam.

Foram exercitados `npc_dialogue`, `session_assessment`, `knowledge_extraction`,
`social_speech`, `assembly_debate` e `editorial`. As políticas usam dados públicos
para agir; a auditoria privada só ocorre ao terminar. Tokens offline são estimados
por caracteres e não equivalem ao tokenizer nem ao consumo do Qwen.

## Limite da conclusão

Esta execução demonstra contratos, orquestração e persistência. Não mede
balanceamento com pessoas, qualidade literária ou confiabilidade semântica de um
LLM real. As políticas automatizadas são exaustivas e não representam um jogador
humano. Os resultados anteriores de 100 partidas correspondem à versão anterior;
não foram reapresentados como validação deste protocolo.

**O novo caminho ainda não foi executado contra o Qwen/Mantle real.** A última
verificação da credencial local indicava login AWS expirado. `tool_choice="auto"`
usa suporte documentado, mas a taxa real de emissão de ferramentas ainda precisa
ser medida. A [documentação do protocolo](saida_nativa_llm.md) registra essa
limitação. Nenhuma inferência paga foi executada nesta correção.

O runner atual usa somente inferência real. Consulte o [guia de execução](simulacao_partidas_refatoracao.md)
para credenciais e limites; o limite do CLI cobre somente Floriano, enquanto
o consumo dos NPCs e demais agentes do servidor é contabilizado separadamente.
A bateria histórica offline não substitui essa etapa.
