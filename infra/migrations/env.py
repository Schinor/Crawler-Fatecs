"""Ambiente do Alembic: usa as tabelas de `fatecorg_core.db` e a URL do `.env`."""

from alembic import context

from fatecorg_core.db import Base, criar_engine

config = context.config
# Os testes passam a URL por aqui; no uso normal ela vem de DATABASE_URL
url = config.attributes.get("url") or config.get_main_option("sqlalchemy.url")


def rodar_offline() -> None:
    """Gera o SQL sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=url or criar_engine().url.render_as_string(hide_password=False),
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    engine = criar_engine(url)
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
