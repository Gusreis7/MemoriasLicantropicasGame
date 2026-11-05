# Iluminação, horário e caminhada

Os cinco locais possuem uma arte de manhã (09h) e outra de pôr do sol (18h), com a mesma composição, chão e área lógica de 960×360. Os dez PNGs opacos de 2048×768 estão em `frontend/public/assets/locations/`:

| Local | Manhã | Pôr do sol |
| --- | --- | --- |
| Praça Verde | `praca_verde-09h.png` | `praca_verde-18h.png` |
| Cabana da Capitu | `cabana_capitu-09h.png` | `cabana_capitu-18h.png` |
| Casa Verde | `casa_verde-09h.png` | `casa_verde-18h.png` |
| Café do Largo | `cafe_largo-09h.png` | `cafe_largo-18h.png` |
| Cais das Lanternas | `cais_lanternas-09h.png` | `cais_lanternas-18h.png` |

As quatro imagens originalmente diurnas foram reutilizadas por cópia na manhã; o cais original foi reutilizado no pôr do sol. As cinco contrapartes foram produzidas com **image_gen built-in**, usando as imagens existentes como referência e editando a iluminação. Os arquivos originais e seus caminhos continuam disponíveis. [Manifesto dos locais](../frontend/public/assets/locations/manifest.json) e [prompts completos/proveniência](../frontend/public/assets/locations/lighting-prompts.json) registram dimensões, fontes e hashes.

`frontend/game/daylight.ts` resolve os pares. A cena carrega as duas imagens e mantém as camadas nas mesmas coordenadas, sem refazer o cenário a cada atualização do servidor. A manhã permanece até as 15h; a opacidade da arte de pôr do sol cresce suavemente entre 15h e 18h. A troca de local utiliza o mesmo progresso do dia.

## Hora da cidade

Os 300 segundos reais continuam controlados pelo servidor. A interface converte esse período para 09:00–18:00: cada segundo real equivale a 1,8 minuto do jogo. A contagem de espera da noite continua em segundos reais.

| Tempo real decorrido | Hora da cidade |
| --- | --- |
| 0:00 | 09:00 |
| 1:40 | 12:00 |
| 2:30 | 13:30 |
| 3:20 | 15:00 |
| 4:10 | 16:30 |
| 5:00 | 18:00 |

`CaseClock` usa o intervalo entre `server_time` e `phase_ends_at`, avançando localmente com relógio monotônico. Recarregar ou viajar não reinicia o horário. Durante a assembleia, a diferença entre o prazo da fase e o prazo do debate informa a parcela diurna pausada; horário e iluminação ficam congelados até a votação. Nenhuma regra, duração ou contrato de backend foi alterado nesta entrega.

## Caminhada de Floriano

O atlas anterior quase repetia a mesma perna adiantada. A nova sheet contém duas poses de repouso e oito fases alternando as duas pernas, com contato, apoio e passagem do pé e braços em oposição. A identidade, a roupa e a exibição de 64×88 foram preservadas.

O PNG [player.png](../frontend/public/assets/characters/player.png) tem 1635×962 e transparência real. [player.json](../frontend/public/assets/characters/player.json) contém dez recortes medidos, canvas virtual de 374×528 e pés alinhados na baseline 499. Somente a entrada `player` foi atualizada no manifesto de personagens. A cena reproduz o ciclo a 12 quadros por segundo enquanto o personagem se desloca e retorna ao repouso quando para, encontra uma borda ou está com os controles bloqueados. Os NPCs mantêm seus próprios assets e animações.

Prompt completo, referência, origem, medidas e hash estão em [player-walk-prompts.json](../frontend/public/assets/characters/player-walk-prompts.json). A arte foi gerada por **image_gen built-in** e copiada sem edição de pixels por script.

## Verificação

- **56 testes frontend aprovados**, incluindo conversão de horário, pausa/retomada da assembleia, limites da iluminação e correspondência dos dez PNGs com o manifesto.
- **Build TypeScript/Vite aprovado.**
- **Quatro cenários Brave aprovados:** montagem real dos cinco locais nos dois horários e oito frames de caminhada; parada na borda, inversão de direção e bloqueio; relógio na interface com retomada após recarregar; fluxos existentes de investigação/detenção/noite e retorno à nova manhã.
- Artes inspecionadas no cenário, dimensões e transparência do atlas conferidas; testes usam tempo, movimento e respostas controlados, sem chamadas AWS.

Capturas locais: `artifacts/lighting-{id}-{09h,18h}.png` e `artifacts/lighting-clock-afternoon.png`. As alterações anteriores e o trabalho de backend em andamento foram preservados.
