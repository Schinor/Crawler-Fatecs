import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { Coleta, StatusColeta, Unidade } from '../../api/tipos';

const ROTULOS: Record<StatusColeta, string> = {
  novo_ppc: 'Documento novo',
  sem_mudanca: 'Sem mudança',
  sem_ppc: 'Documento não encontrado',
  erro_http: 'Erro ao ler o site',
  erro_drive: 'Bloqueado no Drive',
  nao_pdf: 'Formato não aceito',
};
const OK: readonly StatusColeta[] = ['novo_ppc', 'sem_mudanca'];

interface Situacao {
  status: StatusColeta;
  rotulo: string;
  ok: boolean;
  quantidade: number;
}

interface CursoColetado {
  chave: string;
  unidade: string;
  curso: string;
  nome: string;
  iniciadaEm: string;
  situacoes: Situacao[];
  erros: string[];
  comProblema: boolean;
}

/** Junta os resultados da última rodada em uma linha por curso. */
function porCurso(coletas: readonly Coleta[]): CursoColetado[] {
  const grupos = new Map<string, Coleta[]>();
  for (const c of coletas) {
    const chave = `${c.unidade_slug}/${c.curso_slug}`;
    grupos.set(chave, [...(grupos.get(chave) ?? []), c]);
  }
  return [...grupos].map(([chave, lista]) => {
    const contagem = new Map<StatusColeta, number>();
    lista.forEach((c) => contagem.set(c.status, (contagem.get(c.status) ?? 0) + 1));
    const situacoes = [...contagem].map(([status, quantidade]) => ({
      status,
      rotulo: ROTULOS[status] ?? status,
      ok: OK.includes(status),
      quantidade,
    }));
    const erros = lista.map((c) => c.detalhe?.['erro']).filter((e) => typeof e === 'string');
    return {
      chave,
      unidade: lista[0].unidade_slug,
      curso: lista[0].curso_slug,
      nome: lista[0].curso_slug === '-' ? 'Página inicial da unidade' : lista[0].curso_nome,
      iniciadaEm: lista[0].iniciada_em,
      situacoes,
      erros: [...new Set(erros as string[])],
      comProblema: situacoes.some((s) => !s.ok),
    };
  });
}

/** Painel de saúde do crawler: o resultado da rodada mais recente de cada curso. */
@Component({
  selector: 'app-coletas',
  imports: [DatePipe, RouterLink],
  templateUrl: './coletas.html',
})
export class Coletas {
  private readonly api = inject(Api);

  private readonly coletas = httpResource<Coleta[]>(() => this.api.url('/coletas'), {
    defaultValue: [],
  });
  private readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });

  protected readonly soProblemas = signal(false);
  protected readonly carregando = this.coletas.isLoading;
  protected readonly cursos = computed(() => porCurso(this.coletas.value()));
  protected readonly comProblema = computed(() => this.cursos().filter((c) => c.comProblema));
  protected readonly visiveis = computed(() =>
    this.soProblemas() ? this.comProblema() : this.cursos(),
  );
  protected readonly nomesUnidades = computed(
    () => new Map(this.unidades.value().map((u) => [u.slug, u.nome])),
  );
  protected readonly erro = computed(() => {
    const e = this.coletas.error() ?? this.unidades.error();
    return e ? mensagemDeErro(e) : null;
  });

  protected alternar(evento: Event): void {
    this.soProblemas.set((evento.target as HTMLInputElement).checked);
  }
}
