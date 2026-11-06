# Áudio do jogo

Ambiente diurno de pássaros, noturno de grilos e efeitos de papel, caderno, vestígios, passos alternados, aproximação, golpe e impacto usam arquivos CC0 locais. Créditos, autores e downloads em [CREDITS.md](../frontend/public/assets/audio/CREDITS.md). Não há dependência de serviços externos em execução.

O som começa no gesto de iniciar/continuar o caso. Volume inicial 45%; o fundo usa 28% desse volume, com efeitos discretos. Volume e mute persistem no armazenamento local. A aba oculta pausa ambiente e efeitos; voltar retoma somente o ambiente. Trocar dia/noite pausa o loop anterior. Falhas de carregamento ou autoplay não impedem a investigação.

API para as cenas: `gameAudio.setNight(boolean)`, `gameAudio.effect('sneak' | 'slash' | 'impact', variant)`; também `paper`, `close`, `clue`, `step`. `variant` alterna as duas gravações de golpe; a sequência visual pode escolher uma por variação. `start`, `stop`, `unlock`, `setVolume`, `setMuted` controlam o ciclo de vida. Máximo seis efeitos simultâneos, passos limitados a um por 280ms e disparados apenas ao deslocamento real. O módulo não deduz nem revela identidade de NPCs.
