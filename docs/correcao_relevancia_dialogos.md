# Relevância e voz nos diálogos

O harness orienta a persona a responder à mensagem atual. Saudações, crenças e
opiniões não precisam produzir pistas. Apoios de conversa são selecionados pelo
assunto; apresentar um objeto não o transforma em descoberta do NPC.

O mestre verifica eventos inventados, confidências indevidas, narração externa,
tratamento incorreto e mudança de assunto. O reparo devolve códigos autorizados
à própria persona; não escreve uma fala substituta. Falhas esgotadas geram um
fallback técnico identificado. Esse texto permanece no histórico, mas não
alimenta fofocas, relatos úteis ou confissões.

Memórias próprias e encontros recentes explicam sentimentos e reações. O histórico
é lido como texto canônico; molduras antigas não são decodificadas nem reescritas.
O contrato de saída usa ferramentas nativas e `PydanticToolsParser`, sem pedidos
de JSON nos prompts. Veja [os contratos](contratos_llm_estruturados.md),
[o grafo](grafo_dialogo_llm.md) e [as partidas completas](simulacao_partidas_refatoracao.md).

O runner anterior de amostras de diálogo foi removido junto dos experimentos
substituídos. A bateria offline valida integração e limites, sem comprovar
qualidade narrativa ou fundamentação de todas as falas do Qwen.
