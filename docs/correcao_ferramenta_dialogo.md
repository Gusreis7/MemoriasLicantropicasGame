# Correção do fallback nas conversas — 05/11/2026

O jogo repetia «Não consegui organizar minha resposta agora, detetive» mesmo com
credencial válida. Os eventos da partida afetada mostraram duas tentativas por
mensagem, `invalid_tool_response` e nenhuma passagem pelo mestre.

O servidor enviava o contrato de fala em `tools`, mas utilizava `tool_choice="auto"`.
O Qwen podia responder diretamente em texto, sem chamar `NpcSpeech`. A validação
rejeitava essa resposta e persistia o fallback técnico. Portanto, HTTP 200 do
provedor e disponibilidade de credenciais não demonstravam uma fala aceita.

## Alteração

O caminho estruturado passa a enviar `tool_choice="required"` e uma instrução
system separada exigindo exatamente a ferramenta declarada. O prompt de domínio,
o histórico e o schema continuam preservados. Não há extração de JSON do texto,
remoção de cercas nem aceitação de resposta fora do contrato.

O transporte aceita `auto` e `required`; o gerador usa `required`. Ferramenta nomeada
permanece rejeitada: no teste real dessa opção, o provedor respondeu HTTP 200 e
texto livre. A solicitação obrigatória tampouco substitui validação Pydantic,
revisão semântica, guardas ou limites de tentativas. O suporte depende do par
modelo/endpoint e não representa garantia de confiabilidade de 100%.

## Verificação

- **834 testes e sete subtestes passaram**, incluindo preservação do histórico,
  ferramenta obrigatória no transporte, rejeição de texto sem ferramenta,
  cancelamento e medição.
- Aplicação Docker reconstruída, sem resetar o Redis.
- Uma partida nova foi criada pela API pública; Floriano caminhou até Rubião com
  intenções de movimento reais e enviou uma saudação e uma pergunta sobre Brás Cubas.
- As duas mensagens produziram falas de Rubião. O grafo registrou geração, revisão
  do mestre, reparo semântico, guarda e persistência: duas mensagens com
  `generation_status="accepted"`, `fallback=false` e `error_code=null`.
- Evidência local: `artifacts/dialogue-fix-real.json`. A amostra é pequena e não
  constitui avaliação de todas as personas ou de uma partida completa.

Mensagens de fallback já gravadas continuam no histórico. Elas permanecem
identificadas como técnicas e não são convertidas retroativamente em conhecimento.
