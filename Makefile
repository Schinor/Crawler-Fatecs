.PHONY: setup env lint test infra-up infra-down garage-init crawl

setup:      ## instala todas as dependências Python do workspace
	uv sync --all-packages

env:        ## cria o .env local com segredos aleatórios (não sobrescreve)
	bash scripts/gerar-env.sh

lint:       ## lint + checagem de formatação
	uv run ruff check .
	uv run ruff format --check .

test:       ## roda todos os testes Python
	uv run pytest

COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

infra-up:   ## sobe Postgres e Garage e cria o bucket
	$(COMPOSE) up -d
	bash scripts/garage-init.sh

infra-down:
	$(COMPOSE) down

garage-init: ## (re)configura layout, chave e bucket do Garage
	bash scripts/garage-init.sh

crawl:      ## coleta uma unidade: make crawl U=pompeia
	uv run fatecorg-crawler run --unidade $(U)
