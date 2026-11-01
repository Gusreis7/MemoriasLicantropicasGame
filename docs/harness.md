# Harness individual e Bedrock Mantle

Registro da primeira entrega. Para o novo fluxo HTTP, projeções estratégicas e tokens de perfil AWS, consulte [conversa_jogador_persona.md](conversa_jogador_persona.md). Os limites descritos abaixo se referem ao harness interno original.

Branch: `feat/harness_mantle`. Contratos compartilhados em [contratos_agentes.md](contratos_agentes.md).

## Plano executado

1. Implementar o adaptador assíncrono `BedrockMantleClient` sobre HTTP Chat Completions.
2. Implementar `HarnessService` com validação de participantes, contexto individual e memória.
3. Documentar configuração, limites e extensão futura, sem executar testes ou inferências.

## Interfaces de composição

```python
BedrockMantleClient(
    base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
    api_key=None,  # str, SecretStr ou None; configurar com segredo do ambiente
    model="qwen.qwen3-32b",
    timeout_seconds=30.0,
    max_tokens=512,
)
HarnessService(characters, games, memory, llm, history_limit=20)
```

O adaptador expõe `complete(messages)` e `aclose()`. O harness expõe `respond(game_id, npc_id, conversation_id, speaker_id, text) → HarnessReply`. São serviços internos; não há novo endpoint de diálogo nesta entrega. A composição da aplicação fecha o cliente HTTP no encerramento.

O construtor não conecta à AWS. A ausência de API key só gera `LLMUnavailableError` quando uma inferência é solicitada. A credencial é uma API key Bedrock bearer, mantida como `SecretStr`, enviada apenas no header de autorização. Não são implementados SigV4, credenciais Qwen Cloud ou leitura automática de arquivos de credenciais.

O endpoint é HTTPS, sem credenciais embutidas, query string ou fragmentos. A configuração controla explicitamente raiz, modelo, timeout e limite de saída (1–8192 tokens). O cliente acrescenta `chat/completions` à raiz e não segue redirects.

## Fluxo de uma resposta

1. Validar mensagem não vazia de até 8000 caracteres, partida existente e NPC vivo.
2. Validar interlocutor: `player` ou outro NPC vivo da mesma partida. Ninguém pode conversar consigo mesmo.
3. Obter ou criar conversa com par imutável de participantes. Em disputa de criação, reler a conversa e conferir o par antes de continuar.
4. Recuperar até `history_limit` mensagens dessa conversa usando o NPC atual como observador autorizado.
5. Construir uma projeção privada do personagem: somente sua ficha, seu objetivo ativo e o que acredita sobre sua condição. O elenco e os papéis dos outros NPCs nunca entram no prompt.
6. Fazer uma inferência e validar a resposta textual.
7. Persistir pergunta e resposta em lote atômico na memória. Se a inferência falhar, não gravar mensagens parciais; pode existir apenas o registro vazio da conversa.

Para outro NPC responder à mesma conversa, o chamador interno inverte `npc_id`/`speaker_id` e fornece a fala recebida. Isso não agenda encontros nem cria ciclos autônomos.

## Contexto e privacidade

Um NPC civil recebe seu objetivo civil. O lobisomem consciente recebe apenas seu próprio objetivo como lobisomem e instrução de ocultar sua condição. Para um personagem em negação, o prompt não declara o papel real nem inclui seu objetivo secreto como lobisomem: fornece o objetivo civil e sintomas de lapsos/medo de enlouquecer. Os efeitos noturnos dessa condição pertencem ao futuro motor de regras.

Histórico usa `assistant` para falas do próprio NPC e `user` para o interlocutor, com remetente explícito em JSON. A entrada atual também é dado estruturado de conversa; não pode conceder permissões. O prompt estabelece época e voz literária, diferencia relatos de fatos e não autoriza inventar crimes ou pistas como acontecimentos reais. Essas instruções reduzem erros narrativos, mas não são garantia de que todo texto gerado manterá segredo; a API não expõe o harness publicamente nesta base.

O limite padrão é 20 mensagens. O contexto inclui somente a cauda cronológica que caiba em 24000 caracteres de histórico; não apaga ou resume os registros originais. Esse limite é uma aproximação por caracteres, não um tokenizador. Excesso de contexto ainda pode ser rejeitado pelo provedor e deve ser calibrado com uso real.

## Falhas e limites desta versão

- Uma requisição ao provedor por resposta; sem retries automáticos, tools, streaming ou loops de agentes.
- Timeout, status HTTP não exitoso, formato inválido, conteúdo vazio, contagens de tokens inválidas, `finish_reason` diferente de `stop` ou pedido de ferramenta produzem `LLMUnavailableError` sem payload, credencial ou prompt na mensagem de erro.
- A saída pública é somente `message.content`; campos de raciocínio eventualmente retornados pelo modelo não são persistidos nem enviados ao jogador.
- `HarnessReply` traz modelo e contagens opcionais de tokens para observabilidade interna.
- IDs de mensagens são únicos; Redis deduplica mensagens por ID, mas repetir `respond()` não reutiliza a mesma inferência nem os mesmos IDs. O serviço não oferece idempotência da requisição inteira.
- Não há lock de conversa. Chamadas concorrentes podem usar o mesmo histórico anterior; o chamador deve aguardar uma resposta antes de iniciar a próxima. Serialização/replay são evolução futura.
- O harness não aplica ações de jogo, não muda papéis e não realiza encontros ou mortes. Tool calling será acrescentado junto às ações de domínio e às respectivas permissões.
- Autorização da sessão do jogador fica a cargo de uma futura camada de identidade. `speaker_id` não deve ser aceito livremente de um cliente HTTP.

## Modelo e uso gratuito

O modelo previsto é `qwen.qwen3-32b` no Mantle, conforme [ficha oficial AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html). O usuário pretende utilizar o benefício gratuito/créditos da própria conta; a gratuidade não é uma propriedade garantida pelo adaptador. A [página de preços](https://aws.amazon.com/bedrock/pricing/) lista custos de inferência. Elegibilidade e saldo da conta só poderão ser confirmados posteriormente.

Nenhum teste, servidor, container ou inferência foi executado nesta frente, conforme solicitado. A validação após configurar credenciais deverá confirmar região, autenticação, formato real da resposta, consumo e voz dos personagens.
