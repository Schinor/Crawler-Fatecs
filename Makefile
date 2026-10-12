.PHONY: setup lint test infra-up infra-down crawl

setup:      ## instala todas as dependências Python do workspace
	uv sync --all-packages

lint:       ## lint + checagem de formatação
	uv run ruff check .
	uv run ruff format --check .

test:       ## roda todos os testes Python
	uv run pytest

infra-up:   ## sobe Postgres e MinIO
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

crawl:      ## coleta uma unidade: make crawl U=pompeia
	uv run bd-ppcs-crawler run --unidade $(U)
