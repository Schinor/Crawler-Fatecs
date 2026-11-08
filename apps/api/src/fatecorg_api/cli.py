"""Administração das contas: `uv run fatecorg-api --help`. Não há cadastro aberto pela API."""

import sys
from typing import Annotated

import typer

from fatecorg_api.auth import SENHA_MINIMA, gerar_hash
from fatecorg_core.db import criar_engine, sessao
from fatecorg_core.domain import Perfil
from fatecorg_core.repositories import EmailJaCadastrado, UnidadeObrigatoria, UsuarioRepo

app = typer.Typer(no_args_is_help=True, add_completion=False)
OpcaoSenhaStdin = Annotated[
    bool, typer.Option("--senha-stdin", help="Lê a senha da entrada padrão (scripts)")
]


def _ler_senha(da_stdin: bool) -> str:
    """Nunca por argumento: a senha ficaria no histórico do shell e na lista de processos."""
    if da_stdin:
        senha = sys.stdin.readline().rstrip("\n")
    else:
        senha = typer.prompt("Senha", hide_input=True, confirmation_prompt=True)
    if not SENHA_MINIMA <= len(senha) <= 128:
        typer.echo(f"A senha precisa ter de {SENHA_MINIMA} a 128 caracteres.", err=True)
        raise typer.Exit(1)
    return senha


@app.command("criar-usuario")
def criar_usuario(
    email: Annotated[str, typer.Option()],
    nome: Annotated[str, typer.Option()],
    perfil: Annotated[Perfil, typer.Option()],
    unidade: Annotated[str | None, typer.Option(help="Slug; obrigatório para coordenador")] = None,
    senha_stdin: OpcaoSenhaStdin = False,
) -> None:
    """Cria uma conta (use para o primeiro admin do polo)."""
    senha_hash = gerar_hash(_ler_senha(senha_stdin))
    try:
        with sessao(criar_engine()) as s:
            usuario = UsuarioRepo(s).criar(email, nome, senha_hash, perfil, unidade)
    except EmailJaCadastrado:
        typer.echo("Já existe uma conta com esse e-mail.", err=True)
        raise typer.Exit(1) from None
    except (UnidadeObrigatoria, LookupError) as erro:
        typer.echo(
            f"{erro}. Rode a coleta ou a importação antes, se o banco estiver vazio.", err=True
        )
        raise typer.Exit(1) from None
    typer.echo(f"Conta {usuario.id} criada: {usuario.perfil.value}.")


@app.command("redefinir-senha")
def redefinir_senha(
    email: Annotated[str, typer.Option()],
    senha_stdin: OpcaoSenhaStdin = False,
) -> None:
    """Troca a senha, desbloqueia a conta e encerra as sessões abertas."""
    senha_hash = gerar_hash(_ler_senha(senha_stdin))
    with sessao(criar_engine()) as s:
        achou = UsuarioRepo(s).redefinir_senha(email, senha_hash)
    if not achou:
        typer.echo("Não há conta com esse e-mail.", err=True)
        raise typer.Exit(1)
    typer.echo("Senha trocada; as sessões abertas foram encerradas.")
