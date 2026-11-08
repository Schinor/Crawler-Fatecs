"""Ambiente do Alembic: usa as tabelas de `fatecorg_core.db` e a URL do `.env`."""

from alembic import context

from fatecorg_core.db import Base, criar_engine

config = context.config
# Os testes passam a URL por aqui; no uso normal ela vem de DATABASE_URL
url = config.attributes.get("url") or config.get_main_option("sqlalchemy.url")

# Índices de expressão que o autogenerate não sabe comparar: são mantidos à mão nas migrations
# (o de busca está na 0002). Sem isto, `alembic check` pediria para removê-los.
INDICES_MANUAIS = {"ix_ppc_versao_busca"}


def incluir(objeto, nome, tipo, refletido, comparado_com) -> bool:
    return not (tipo == "index" and nome in INDICES_MANUAIS)


def rodar_offline() -> None:
    """Gera o SQL sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=url or criar_engine().url.render_as_string(hide_password=False),
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
        include_object=incluir,
    )
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    engine = criar_engine(url)
    with engine.connect() as conexao:
        context.configure(
            connection=conexao,
            target_metadata=Base.metadata,
            compare_type=True,
            include_object=incluir,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
