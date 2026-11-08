import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { Aviso, Unidade, Versao } from '../../api/tipos';
import { AvisosBanner } from '../../shared/avisos-banner';
import {
  RotuloOrigemPipe,
  RotuloTipoPipe,
  TamanhoPipe,
  agruparPorTipo,
} from '../../shared/formatos';

/** Histórico de um curso: as versões de cada documento, da mais recente para a mais antiga. */
@Component({
  selector: 'app-curso',
  imports: [DatePipe, RouterLink, AvisosBanner, RotuloOrigemPipe, RotuloTipoPipe, TamanhoPipe],
  templateUrl: './curso.html',
})
export class Curso {
  /** Vêm da rota `unidades/:unidade/cursos/:curso` (withComponentInputBinding). */
  readonly unidade = input.required<string>();
  readonly curso = input.required<string>();

  protected readonly api = inject(Api);

  protected readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });
  protected readonly versoes = httpResource<Versao[]>(
    () => ({
      url: this.api.url('/ppcs'),
      params: { unidade: this.unidade(), curso: this.curso(), limite: 200 },
    }),
    { defaultValue: [] },
  );
  protected readonly avisos = httpResource<Aviso[]>(
    () => ({
      url: this.api.url('/avisos'),
      params: { unidade: this.unidade(), curso: this.curso() },
    }),
    { defaultValue: [] },
  );

  protected readonly cadastro = computed(() => {
    const u = this.unidades.value().find((x) => x.slug === this.unidade());
    return { unidade: u, curso: u?.cursos.find((c) => c.slug === this.curso()) };
  });
  protected readonly grupos = computed(() => agruparPorTipo(this.versoes.value()));
  protected readonly erro = computed(() => {
    const e = this.versoes.error() ?? this.unidades.error() ?? this.avisos.error();
    return e ? mensagemDeErro(e) : null;
  });
}
