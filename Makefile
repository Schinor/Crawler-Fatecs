.PHONY: setup env lint test infra-up infra-down garage-init migrate migration crawl \
	coleta-semanal agendar agendamento desagendar

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

migrate:    ## aplica as migrations no banco do .env (rode depois do infra-up)
	uv run alembic upgrade head

migration:  ## gera migration a partir das tabelas: make migration M="descrição"
	uv run alembic revision --autogenerate -m "$(M)"

usuario:    ## cria uma conta: make usuario E=email N="Nome" P=admin_polo [U=pompeia]
	uv run fatecorg-api criar-usuario --email "$(E)" --nome "$(N)" --perfil "$(P)" $(if $(U),--unidade "$(U)")

crawl:      ## coleta uma unidade: make crawl U=pompeia
	uv run fatecorg-crawler run --unidade $(U)

coleta-semanal: ## roda agora a rodada agendada (todas as unidades, log em data/logs/)
	bash scripts/coleta-semanal.sh

agendar:    ## agenda a coleta semanal nesta máquina (domingo 03h; systemd ou cron)
	bash scripts/agendar.sh instalar

agendamento: ## mostra a próxima execução e o último log
	bash scripts/agendar.sh status

desagendar: ## remove o agendamento desta máquina
	bash scripts/agendar.sh remover
