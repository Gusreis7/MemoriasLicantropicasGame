# Áudio do jogo

Ambiente diurno de pássaros, noturno de grilos e efeitos de papel, caderno, vestígios, passos alternados, aproximação, golpe e impacto usam arquivos CC0 locais. Créditos, autores e downloads em [CREDITS.md](../frontend/public/assets/audio/CREDITS.md). Não há dependência de serviços externos em execução.

O som começa no gesto de iniciar/continuar o caso. Volume inicial 45%; o fundo usa 28% desse volume, com efeitos discretos. Volume e mute persistem no armazenamento local. A aba oculta pausa ambiente e efeitos; voltar retoma somente o ambiente. Trocar dia/noite pausa o loop anterior. Falhas de carregamento ou autoplay não impedem a investigação.

API para as cenas: `gameAudio.setNight(boolean)`, `gameAudio.effect('sneak' | 'slash' | 'impact', variant)`; também `paper`, `close`, `clue`, `step`. `variant` alterna as duas gravações de golpe; a sequência visual pode escolher uma por variação. `start`, `stop`, `unlock`, `setVolume`, `setMuted` controlam o ciclo de vida. Máximo seis efeitos simultâneos, passos limitados a um por 280ms e disparados apenas ao deslocamento real. O módulo não deduz nem revela identidade de NPCs.

Revisão do ataque: `gameAudio.effect('howl')` toca uivo editado de 3.3 segundos, com volume relativo de 40% do volume geral e normalização moderada. `effect('impact', variant)` seleciona quatro impactos orgânicos distintos (0–3), mais encorpados que o corte seco inicial. `stopCinematicEffects()` interrompe uivo, aproximação, corte e impacto em skip/cancelamento sem pausar o ambiente e efeitos de interface. A integração da sequência deve chamá-lo no cleanup/finally; mute, aba oculta e encerramento também interrompem todos os efeitos. Os novos arquivos são CC0 tratados offline conforme créditos locais.
