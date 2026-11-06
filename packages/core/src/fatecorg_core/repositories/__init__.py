"""Repositórios: leem e gravam o domínio no banco. Quem chama controla a transação (`sessao`).

Entram e saem entidades de `domain` (`PPCEncontrado`, `Coleta`, `Aviso`), não linhas do banco,
para que crawler e API não dependam do formato das tabelas.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from fatecorg_core.db import AvisoDB, ColetaDB, CursoDB, PPCVersaoDB, UnidadeDB
from fatecorg_core.domain import Aviso, Coleta, PPCEncontrado, TipoDocumento, Unidade

SEM_CURSO = "-"  # curso_slug das coletas que falharam na home da unidade


class UnidadeDesconhecida(LookupError):
    pass


class CatalogoRepo:
    """Unidades e cursos. O seed (`unidades.yaml`) é a fonte; o banco espelha."""

    def __init__(self, s: Session):
        self.s = s

    def sincronizar(self, unidades: list[Unidade]) -> None:
        """Cria ou atualiza unidades e cursos do seed. Nunca apaga: o histórico depende deles."""
        for u in unidades:
            db = self.unidade(u.slug) or UnidadeDB(slug=u.slug)
            db.nome, db.cidade, db.site_url = u.nome, u.cidade, str(u.site_url)
            db.plataforma, db.ativa = u.plataforma, u.ativa
            self.s.add(db)
            self.s.flush()
            for c in u.cursos:
                self.curso(u.slug, c.slug, c.nome, str(c.url))

    def listar(self) -> list[Unidade]:
        unidades = self.s.scalars(
            select(UnidadeDB).options(selectinload(UnidadeDB.cursos)).order_by(UnidadeDB.slug)
        )
        return [
            Unidade.model_validate(
                {
                    "slug": u.slug,
                    "nome": u.nome,
                    "cidade": u.cidade,
                    "site_url": u.site_url,
                    "plataforma": u.plataforma,
                    "ativa": u.ativa,
                    "cursos": [
                        {"slug": c.slug, "nome": c.nome, "url": c.pagina_url or u.site_url}
                        for c in sorted(u.cursos, key=lambda c: c.slug)
                    ],
                }
            )  # fmt: skip
            for u in unidades
        ]

    def curso_existente(self, unidade_slug: str, curso_slug: str) -> CursoDB | None:
        return self.s.scalar(
            select(CursoDB)
            .join(CursoDB.unidade)
            .where(UnidadeDB.slug == unidade_slug, CursoDB.slug == curso_slug)
        )

    def unidade(self, slug: str) -> UnidadeDB | None:
        return self.s.scalar(select(UnidadeDB).where(UnidadeDB.slug == slug))

    def curso(
        self,
        unidade_slug: str,
        curso_slug: str,
        nome: str | None = None,
        pagina_url: str | None = None,
    ) -> CursoDB:
        """Busca o curso; cria se não existir (o adaptador pode descobrir cursos fora do seed)."""
        unidade = self.unidade(unidade_slug)
        if unidade is None:
            raise UnidadeDesconhecida(f"unidade '{unidade_slug}' não está no banco")
        curso = self.s.scalar(
            select(CursoDB).where(CursoDB.unidade_id == unidade.id, CursoDB.slug == curso_slug)
        )
        if curso is None:
            curso = CursoDB(unidade=unidade, slug=curso_slug, nome=nome or curso_slug)
            self.s.add(curso)
        elif nome:
            curso.nome = nome
        if pagina_url:
            curso.pagina_url = pagina_url
        self.s.flush()
        return curso


class VersaoRepo:
    def __init__(self, s: Session):
        self.s = s
        self.catalogo = CatalogoRepo(s)

    def _consulta(self, unidade_slug: str | None = None, curso_slug: str | None = None):
        q = (
            select(PPCVersaoDB)
            .join(PPCVersaoDB.curso)
            .join(CursoDB.unidade)
            .options(joinedload(PPCVersaoDB.curso).joinedload(CursoDB.unidade))
        )
        if unidade_slug:
            q = q.where(UnidadeDB.slug == unidade_slug)
        if curso_slug:
            q = q.where(CursoDB.slug == curso_slug)
        return q

    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool:
        q = self._consulta(unidade_slug, curso_slug).where(PPCVersaoDB.sha256 == sha256)
        return self.s.scalar(q.limit(1)) is not None

    def registrar(self, ppc: PPCEncontrado) -> None:
        curso = self.catalogo.curso(
            ppc.unidade_slug, ppc.curso_slug, ppc.curso_nome, str(ppc.pagina_url)
        )
        self.s.add(
            PPCVersaoDB(
                curso=curso, tipo_documento=ppc.tipo_documento, origem=ppc.origem,
                sha256=ppc.sha256, formato=ppc.formato, tamanho_bytes=ppc.tamanho_bytes,
                chave_arquivo=ppc.caminho_local, chave_texto=ppc.caminho_texto,
                paginas=ppc.paginas, precisa_ocr=ppc.precisa_ocr,
                pagina_url=str(ppc.pagina_url),
                arquivo_url=str(ppc.arquivo_url) if ppc.arquivo_url else None,
                titulo_link=ppc.titulo_link, coletado_em=ppc.coletado_em,
            )
        )  # fmt: skip
        self.s.flush()

    def listar(
        self,
        unidade_slug: str | None = None,
        curso_slug: str | None = None,
        *,
        limite: int | None = None,
        deslocamento: int = 0,
    ) -> list[PPCEncontrado]:
        q = self._consulta(unidade_slug, curso_slug).order_by(
            PPCVersaoDB.coletado_em.desc(), PPCVersaoDB.id.desc()
        )
        q = q.offset(deslocamento).limit(limite)
        return [_para_ppc(v) for v in self.s.scalars(q)]

    def buscar(self, unidade_slug: str, curso_slug: str, sha256: str) -> PPCEncontrado | None:
        q = self._consulta(unidade_slug, curso_slug).where(PPCVersaoDB.sha256 == sha256)
        v = self.s.scalar(q)
        return _para_ppc(v) if v else None


class ColetaRepo:
    def __init__(self, s: Session):
        self.s = s
        self.catalogo = CatalogoRepo(s)

    def registrar(self, coleta: Coleta) -> None:
        unidade = self.catalogo.unidade(coleta.unidade_slug)
        if unidade is None:
            raise UnidadeDesconhecida(f"unidade '{coleta.unidade_slug}' não está no banco")
        curso = None
        if coleta.curso_slug != SEM_CURSO:
            pagina = coleta.detalhe.get("pagina_url")
            curso = self.catalogo.curso(
                coleta.unidade_slug, coleta.curso_slug, coleta.curso_nome,
                str(pagina) if pagina else None,
            )  # fmt: skip
        self.s.add(
            ColetaDB(
                unidade_id=unidade.id, curso_id=curso.id if curso else None,
                iniciada_em=coleta.iniciada_em, status=coleta.status, detalhe=coleta.detalhe,
            )
        )  # fmt: skip
        self.s.flush()

    def ultima_rodada(self, unidade_slug: str) -> datetime | None:
        """Início da coleta mais recente da unidade (usado para não importar duas vezes)."""
        q = (
            select(func.max(ColetaDB.iniciada_em))
            .join(UnidadeDB, ColetaDB.unidade_id == UnidadeDB.id)
            .where(UnidadeDB.slug == unidade_slug)
        )
        ultima = self.s.scalar(q)
        if ultima is not None and ultima.tzinfo is None:  # SQLite não guarda o fuso
            ultima = ultima.replace(tzinfo=UTC)
        return ultima


@dataclass
class AvisosAtualizados:
    novos: list[Aviso]  # apareceram agora: geram notificação
    resolvidos: list[Aviso]


class AvisoRepo:
    def __init__(self, s: Session):
        self.s = s
        self.catalogo = CatalogoRepo(s)

    def _abertos(self, unidade_slug: str | None = None, curso_slug: str | None = None):
        q = (
            select(AvisoDB)
            .join(AvisoDB.curso)
            .join(CursoDB.unidade)
            .options(joinedload(AvisoDB.curso).joinedload(CursoDB.unidade))
            .where(AvisoDB.resolvido_em.is_(None))
            .order_by(UnidadeDB.slug, CursoDB.slug, AvisoDB.arquivo_url)
        )
        if unidade_slug:
            q = q.where(UnidadeDB.slug == unidade_slug)
        if curso_slug:
            q = q.where(CursoDB.slug == curso_slug)
        return list(self.s.scalars(q))

    def abertos(
        self, unidade_slug: str | None = None, curso_slug: str | None = None
    ) -> list[Aviso]:
        return [_para_aviso(a) for a in self._abertos(unidade_slug, curso_slug)]

    def atualizar(
        self, da_rodada: list[Aviso], cursos_lidos: set[tuple[str, str]], agora: datetime
    ) -> AvisosAtualizados:
        """Mesma regra do `data/avisos.json` da Fase 1: abre os novos, renova os que continuam
        e resolve os dos cursos lidos nesta rodada que não apareceram mais."""
        abertos = {(a.curso.unidade.slug, a.curso.slug, a.arquivo_url): a for a in self._abertos()}
        novos: list[Aviso] = []
        vistos = set()
        for aviso in da_rodada:
            chave = (aviso.unidade_slug, aviso.curso_slug, str(aviso.arquivo_url))
            vistos.add(chave)
            if chave in abertos:
                abertos[chave].visto_em = aviso.visto_em
                continue
            curso = self.catalogo.curso(aviso.unidade_slug, aviso.curso_slug, aviso.curso_nome)
            self.s.add(
                AvisoDB(
                    tipo=aviso.tipo, curso=curso, tipo_documento=aviso.tipo_documento,
                    pagina_url=str(aviso.pagina_url), arquivo_url=str(aviso.arquivo_url),
                    titulo_link=aviso.titulo_link, mensagem=aviso.mensagem,
                    detectado_em=aviso.detectado_em, visto_em=aviso.visto_em,
                )
            )  # fmt: skip
            novos.append(aviso)

        resolvidos = []
        for (u_slug, c_slug, url), db in abertos.items():
            if (u_slug, c_slug, url) not in vistos and (u_slug, c_slug) in cursos_lidos:
                db.resolvido_em = agora
                resolvidos.append(_para_aviso(db))
        self.s.flush()
        return AvisosAtualizados(novos=novos, resolvidos=resolvidos)

    def resolver_do_curso(
        self,
        unidade_slug: str,
        curso_slug: str,
        agora: datetime,
        tipo_documento: TipoDocumento | None = None,
    ) -> list[Aviso]:
        """Fecha os avisos abertos do curso (ex.: o PPC bloqueado chegou por upload manual)."""
        resolvidos = []
        for db in self._abertos(unidade_slug, curso_slug):
            if tipo_documento and db.tipo_documento != tipo_documento:
                continue
            db.resolvido_em = agora
            resolvidos.append(_para_aviso(db))
        self.s.flush()
        return resolvidos


def _para_ppc(v: PPCVersaoDB) -> PPCEncontrado:
    return PPCEncontrado.model_validate(
        {
            "unidade_slug": v.curso.unidade.slug,
            "curso_slug": v.curso.slug,
            "curso_nome": v.curso.nome,
            "tipo_documento": v.tipo_documento,
            "origem": v.origem,
            "pagina_url": v.pagina_url or v.curso.pagina_url or v.curso.unidade.site_url,
            "arquivo_url": v.arquivo_url,
            "titulo_link": v.titulo_link,
            "formato": v.formato,
            "sha256": v.sha256,
            "caminho_local": v.chave_arquivo,
            "caminho_texto": v.chave_texto,
            "tamanho_bytes": v.tamanho_bytes,
            "paginas": v.paginas,
            "precisa_ocr": v.precisa_ocr,
            "coletado_em": v.coletado_em,
        }
    )


def _para_aviso(a: AvisoDB) -> Aviso:
    return Aviso.model_validate(
        {
            "tipo": a.tipo,
            "unidade_slug": a.curso.unidade.slug,
            "curso_slug": a.curso.slug,
            "curso_nome": a.curso.nome,
            "tipo_documento": a.tipo_documento,
            "pagina_url": a.pagina_url,
            "arquivo_url": a.arquivo_url,
            "titulo_link": a.titulo_link,
            "mensagem": a.mensagem,
            "detectado_em": a.detectado_em,
            "visto_em": a.visto_em,
        }
    )


__all__ = [
    "AvisoRepo",
    "AvisosAtualizados",
    "CatalogoRepo",
    "ColetaRepo",
    "SEM_CURSO",
    "UnidadeDesconhecida",
    "VersaoRepo",
]
