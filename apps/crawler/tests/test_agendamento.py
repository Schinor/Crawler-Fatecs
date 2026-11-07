"""C9: coleta agendada. Código de saída do `run`, e-mail de falha e os scripts de shell."""

import fcntl
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fatecorg_core.domain import Coleta, StatusColeta
from fatecorg_crawler import cli
from fatecorg_crawler.agendamento import (
    CODIGO_NADA_LIDO,
    montar_email_falha,
    nada_lido,
    redigir,
    segredos,
)

RAIZ = Path(__file__).resolve().parents[3]
COLETA_SEMANAL = RAIZ / "scripts" / "coleta-semanal.sh"
AGENDAR = RAIZ / "scripts" / "agendar.sh"
AGORA = datetime(2026, 11, 8, 3, tzinfo=UTC)


def coleta(status: StatusColeta) -> Coleta:
    return Coleta(
        unidade_slug="pompeia", curso_slug="ads", curso_nome="ADS", iniciada_em=AGORA,
        status=status, detalhe={},
    )  # fmt: skip


def test_nada_lido_so_quando_tudo_e_erro_http():
    assert nada_lido([coleta(StatusColeta.ERRO_HTTP), coleta(StatusColeta.ERRO_HTTP)])
    assert not nada_lido([coleta(StatusColeta.ERRO_HTTP), coleta(StatusColeta.SEM_MUDANCA)])
    assert not nada_lido([])  # nenhuma unidade ativa não é falha de rede


def test_run_sai_com_codigo_2_quando_nenhuma_pagina_foi_lida(monkeypatch, tmp_path):
    class ColetorSemRede:
        def __init__(self, *_):
            pass

        def coletar_unidade(self, _u):
            yield coleta(StatusColeta.ERRO_HTTP)

    monkeypatch.chdir(tmp_path)  # sem .env: sink jsonl em ./data
    monkeypatch.setattr(cli, "Coletor", ColetorSemRede)
    resultado = CliRunner().invoke(cli.app, ["run", "--todas", "--sink", "jsonl"])
    assert resultado.exit_code == CODIGO_NADA_LIDO, resultado.output
    assert "Nenhuma página foi lida" in resultado.output


def test_segredos_pelo_nome_da_variavel():
    # Valores repetitivos de propósito: não parecem segredo para o gitleaks
    falsos = [letra * 10 for letra in "abcd"]
    nomes = ["POSTGRES_PASSWORD", "S3_SECRET_KEY", "API_TOKEN_UPLOAD", "NOTIFICACAO_SMTP_SENHA"]
    ambiente: dict[str, str | None] = dict(zip(nomes, falsos, strict=True))
    ambiente |= {"S3_BUCKET": "ppcs", "CRAWLER_DELAY_SECONDS": "2.0", "S3_ACCESS_KEY": ""}
    assert segredos(ambiente) == set(falsos)


def test_redigir_troca_segredos_e_senha_em_url():
    log = (
        "erro ao conectar: postgresql+psycopg://fatecorg:outra-senha@localhost:5432/x\n"
        "chave xxxxxxxxxx recusada\n"
        "https://fatecpompeia.edu.br/ads ok"
    )
    limpo = redigir(log, {"xxxxxxxxxx"})
    assert "outra-senha" not in limpo
    assert "xxxxxxxxxx" not in limpo
    assert "postgresql+psycopg://fatecorg:***@localhost" in limpo
    assert "https://fatecpompeia.edu.br/ads ok" in limpo


def test_email_de_falha_explica_o_motivo():
    assunto, corpo = montar_email_falha(
        CODIGO_NADA_LIDO, Path("/x/coleta.log"), "linha final", AGORA, "maquina"
    )
    assert "maquina" in assunto
    assert "nenhuma página foi lida" in corpo
    assert corpo.endswith("linha final")
    _, corpo = montar_email_falha(1, Path("/x/coleta.log"), "", AGORA, "maquina")
    assert "código 1" in corpo


def test_notificar_falha_nao_manda_segredo_do_env(monkeypatch, tmp_path):
    enviados: list[str] = []
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "NOTIFICACAO_SMTP_HOST=smtp.exemplo\nNOTIFICACAO_DESTINATARIOS=a@exemplo\n"
        "S3_SECRET_KEY=segredo-do-garage\n"
    )
    monkeypatch.setattr(cli, "enviar_email", lambda _s, _a, corpo: enviados.append(corpo))
    log = tmp_path / "coleta.log"
    log.write_text("Traceback ...\nbotocore: chave segredo-do-garage inválida\n")
    resultado = CliRunner().invoke(cli.app, ["notificar-falha", "--log", str(log), "--codigo", "1"])
    assert resultado.exit_code == 0, resultado.output
    (corpo,) = enviados
    assert "segredo-do-garage" not in corpo
    assert "chave *** inválida" in corpo


# --- scripts/coleta-semanal.sh, com um `uv` falso -------------------------------------------


@pytest.fixture
def uv_falso(tmp_path: Path) -> Path:
    """Registra cada chamada em chamadas.txt; o `run` sai com $CODIGO_RUN (padrão 0)."""
    uv = tmp_path / "uv"
    uv.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >>"$CHAMADAS"\n'
        'case "$*" in *" run --todas"*) echo "rodada falsa"; exit "${CODIGO_RUN:-0}";; esac\n'
    )
    uv.chmod(0o755)
    return uv


def rodar_coleta(tmp_path: Path, uv: Path, **env: str) -> subprocess.CompletedProcess[str]:
    ambiente = {
        **os.environ,
        "FATECORG_UV": str(uv),
        "FATECORG_LOG_DIR": str(tmp_path / "logs"),
        "CHAMADAS": str(tmp_path / "chamadas.txt"),
        **env,
    }
    return subprocess.run(
        ["bash", str(COLETA_SEMANAL)], env=ambiente, capture_output=True, text=True, check=False
    )


def chamadas(tmp_path: Path) -> list[str]:
    arquivo = tmp_path / "chamadas.txt"
    return arquivo.read_text().splitlines() if arquivo.exists() else []


def test_coleta_semanal_ok_grava_log_e_nao_notifica(tmp_path, uv_falso):
    r = rodar_coleta(tmp_path, uv_falso)
    assert r.returncode == 0, r.stderr
    assert chamadas(tmp_path) == ["run --frozen fatecorg-crawler run --todas"]
    (log,) = (tmp_path / "logs").glob("coleta-*.log")
    texto = log.read_text()
    assert "rodada falsa" in texto
    assert "código 0" in texto
    assert log.stat().st_mode & 0o077 == 0  # só o dono lê


def test_coleta_semanal_com_falha_notifica_e_repassa_o_codigo(tmp_path, uv_falso):
    r = rodar_coleta(tmp_path, uv_falso, CODIGO_RUN="2")
    assert r.returncode == 2
    run, notificar = chamadas(tmp_path)
    assert run.endswith("run --todas")
    assert "notificar-falha --log" in notificar
    assert notificar.endswith("--codigo 2")


def test_coleta_semanal_nao_roda_duas_ao_mesmo_tempo(tmp_path, uv_falso):
    logs = tmp_path / "logs"
    logs.mkdir()
    with (logs / ".coleta.lock").open("w") as trava:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = rodar_coleta(tmp_path, uv_falso)
    assert r.returncode == 0
    assert "ainda está rodando" in r.stderr
    assert chamadas(tmp_path) == []


def test_coleta_semanal_guarda_so_os_logs_mais_recentes(tmp_path, uv_falso):
    logs = tmp_path / "logs"
    logs.mkdir()
    for i in range(5):
        antigo = logs / f"coleta-2026-01-0{i + 1}T030000.log"
        antigo.write_text("antigo")
        os.utime(antigo, (1_700_000_000 + i, 1_700_000_000 + i))
    r = rodar_coleta(tmp_path, uv_falso, FATECORG_LOGS_MANTER="3")
    assert r.returncode == 0, r.stderr
    restantes = sorted(p.name for p in logs.glob("coleta-*.log"))
    assert len(restantes) == 3
    assert "coleta-2026-01-05T030000.log" in restantes  # o antigo mais novo fica
    assert "coleta-2026-01-01T030000.log" not in restantes


# --- scripts/agendar.sh ----------------------------------------------------------------------


def rodar_agendar(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    ambiente = {**os.environ, "FATECORG_UV": "/opt/uv", **env}
    return subprocess.run(
        ["bash", str(AGENDAR), *args], env=ambiente, capture_output=True, text=True, check=False
    )


def test_agendar_mostra_timer_de_domingo_as_3h_persistente():
    r = rodar_agendar("mostrar", FATECORG_AGENDADOR="systemd")
    assert r.returncode == 0, r.stderr
    assert "OnCalendar=Sun *-*-* 03:00:00" in r.stdout
    assert "Persistent=true" in r.stdout
    assert f'ExecStart=/usr/bin/env bash "{COLETA_SEMANAL}"' in r.stdout
    assert 'Environment="FATECORG_UV=/opt/uv"' in r.stdout


def test_agendar_mostra_linha_do_cron():
    r = rodar_agendar("mostrar", FATECORG_AGENDADOR="cron")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[1].startswith("0 3 * * 0 cd ")
    assert "# fatecorg-coleta" in r.stdout


def test_agendar_sem_comando_mostra_o_uso():
    r = rodar_agendar()
    assert r.returncode == 64
    assert "uso:" in r.stderr
