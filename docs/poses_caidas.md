# Desfecho visual do ataque

Os oito personagens do manifesto têm uma pose própria em `frontend/public/assets/cinematics/fallen/{id}.png`, gerada individualmente por image_gen built-in a partir da respectiva sheet. Prompts, referências, origem e hashes estão nos arquivos `fallen-{id}.json`. Os recortes de renderização usam os limites visíveis do alfa; nenhum pixel foi retocado por script.

A vítima cai após o impacto e é substituída pela pose horizontal, com olhos fechados e sem gore. O lobisomem uiva e foge usando seu ciclo de caminhada. A imagem caída existe somente no canvas temporário da sequência, destruído antes do jornal; não altera mundo, retratos ou cenas do amanhecer. Floriano tem arte preparada, mas isso não muda as regras de escolha de vítimas do servidor.

O uivo e os quatro impactos usam arquivos CC0 com créditos em `assets/audio/CREDITS.md`. Pular, cancelar ou encerrar interrompe os sons da sequência. Movimento reduzido mostra um breve quadro imóvel sem golpes animados e sem disparar esses efeitos.
