# Limpeza do legado e reinício local

Executada em 05/11/2026, na branch `fix/remove_legacy_state`.

## Código e arquivos retirados

- Leitor de envelopes JSON/Markdown de conversas antigas e reescrita de molduras
  de fala. Histórico atual é texto canônico, validado pela guarda.
- Importação de transcrições anteriores ao outbox, seu marcador e testes de
  migração. A extração consome somente trocas confirmadas na fila atual.
- Matriz antiga e rebase de relações, migração de assuntos e aceitação do catálogo
  anterior. Assuntos e afetos atuais são inicializados uma vez por partida.
- Projeção automática de cenários antigos de 1920px e recriação silenciosa de um
  ciclo ausente. Estado incompatível ou incompleto é rejeitado.
- Onze scripts de benchmarks/amostras substituídos, seus relatórios gerados e
  o runner estático anterior. O runner mantido é `scripts/run_session_simulations.py`.
- Artefatos locais de experimentação, incluindo backups antigos do Redis.

As decisões de design do jogo permanecem documentadas. Artefatos de estudos
retirados do checkout podem ser consultados no histórico Git anterior à limpeza.
Os testes de segurança de conteúdo sem autorização e de campos serializados
continuam ativos: texto fora do contrato é bloqueado, sem extrair sua fala.

## Dados e aplicação

O volume `memoriaslicantropicasgame_redis_data` foi excluído e recriado.
Partidas, conversas, conhecimento, eventos, consumo e sessões admin anteriores
foram apagados. O volume novo foi criado em **05/11/2026 às 13:41:29 -03:00**.
Após a subida e as verificações HTTP, `redis-cli DBSIZE` retornou **0**.

API e frontend foram reconstruídos e iniciados com o launcher local. A imagem
executa `src.main:app`, sem o módulo de histórico legado. Jogo em 7077, admin
em 7078 e API em 7079. O banco da aplicação permaneceu vazio durante os testes,
que usaram Redis separado.

Ao tentar retomar uma partida removida, o navegador descarta a referência local
e o rascunho de assembleia correspondente, oculta a opção de continuar e permite
iniciar uma nova investigação.

## Verificações

- **825 testes e sete subtestes passaram com Redis real** em namespaces isolados.
  A suíte anterior que mantinha migrações foi aposentada nesses pontos; as
  regressões novas exigem rejeitar formatos antigos, em vez de convertê-los.
- **Cinco fluxos passaram no Brave**, incluindo o caso apagado, criação nova,
  retomada, diálogo, navegação e proteção de instruções.
- Build Docker/TypeScript concluído; serviços iniciados. Jogo, admin e health
  responderam HTTP 200; admin pelo gateway público respondeu 404, e API admin
  sem autenticação respondeu 401.
- Nenhuma chamada de inferência AWS foi feita nesta manutenção.

Para repetir um reset completo local:

```sh
make destroy
make setup
```

`make destroy` apaga permanentemente o volume do jogo. Encerrar preservando dados
continua disponível por `make down`.
