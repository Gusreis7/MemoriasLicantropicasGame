.DEFAULT_GOAL := help

COMPOSE := docker compose -f compose.yaml

.PHONY: help setup up down destroy status logs

help: ## Mostra os comandos disponíveis.
	@printf '%s\n' \
	  'Memórias Licantropicas — ambiente Docker' \
	  '' \
	  '  make setup    Primeira subida: configura, constrói e inicia tudo' \
	  '  make up       Inicia usando as imagens já construídas' \
	  '  make down     Derruba os containers e preserva as partidas' \
	  '  make destroy  Derruba os containers e APAGA todas as partidas' \
	  '  make status   Mostra o estado dos serviços' \
	  '  make logs     Acompanha os logs da aplicação'

setup: ## Configura o ambiente, constrói as imagens e inicia os serviços.
	@./scripts/start_local.sh

up: ## Inicia os serviços sem reconstruir as imagens.
	@./scripts/start_local.sh --no-build

down: ## Remove containers e rede, preservando o volume Redis.
	@$(COMPOSE) down --remove-orphans
	@printf '%s\n' 'Aplicação encerrada. As partidas foram preservadas.'

destroy: ## Remove containers, rede e o volume Redis com todas as partidas.
	@printf '%s\n' 'Removendo a aplicação e todas as partidas armazenadas no Redis...'
	@$(COMPOSE) down --volumes --remove-orphans
	@printf '%s\n' 'Aplicação encerrada e dados removidos.'

status: ## Mostra containers ativos e encerrados.
	@$(COMPOSE) ps --all

logs: ## Acompanha os logs de Redis, API, jogo e painel.
	@$(COMPOSE) logs --follow --tail=100 redis api game admin
