"""Linha de comando do crawler: `uv run bd-ppcs-crawler --help`."""

from pathlib import Path

import typer
import yaml

app = typer.Typer(help="Crawler dos PPCs das Fatecs do Polo Regional 08.")
SEEDS = Path(__file__).resolve().parents[2] / "seeds" / "unidades.yaml"


def _carregar_unidades() -> list[dict]:
    return yaml.safe_load(SEEDS.read_text(encoding="utf-8"))["unidades"]


@app.command()
def unidades() -> None:
    """Lista as unidades cadastradas no seed."""
    for u in _carregar_unidades():
        typer.echo(f"{u['slug']:<20} {u['plataforma']:<14} {u['site_url']}")


@app.command()
def run(unidade: str = typer.Option(..., help="slug da unidade, ex.: pompeia")) -> None:
    """Coleta uma unidade (implementação nas tarefas C3 a C6 do plano)."""
    typer.echo(f"TODO: coletar {unidade}")


if __name__ == "__main__":
    app()
