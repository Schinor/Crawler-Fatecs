import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { Aviso, Unidade, Versao } from '../../api/tipos';
import { AvisosBanner } from '../../shared/avisos-banner';

interface Resumo {
  documentos: number;
  ultima?: string;
  avisos: number;
}

/** Página inicial: unidades, seus cursos e a situação de cada um. */
@Component({
  selector: 'app-unidades',
  imports: [DatePipe, RouterLink, AvisosBanner],
  templateUrl: './unidades.html',
})
export class Unidades {
  private readonly api = inject(Api);

  protected readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });
  protected readonly versoes = httpResource<Versao[]>(
    () => ({ url: this.api.url('/ppcs'), params: { limite: 200 } }),
    { defaultValue: [] },
  );
  protected readonly avisos = httpResource<Aviso[]>(() => this.api.url('/avisos'), {
    defaultValue: [],
  });

  protected readonly erro = computed(() => {
    const e = this.unidades.error() ?? this.versoes.error() ?? this.avisos.error();
    return e ? mensagemDeErro(e) : null;
  });

  /** Resumo por `unidade/curso`: quantos documentos, a coleta mais recente e os avisos. */
  protected readonly resumos = computed(() => {
    const mapa = new Map<string, Resumo>();
    const pegar = (chave: string) => {
      let r = mapa.get(chave);
      if (!r) mapa.set(chave, (r = { documentos: 0, avisos: 0 }));
      return r;
    };
    for (const v of this.versoes.value()) {
      const r = pegar(`${v.unidade}/${v.curso}`);
      r.documentos++;
      if (!r.ultima || v.coletado_em > r.ultima) r.ultima = v.coletado_em;
    }
    for (const a of this.avisos.value()) pegar(`${a.unidade_slug}/${a.curso_slug}`).avisos++;
    return mapa;
  });

  protected resumo(unidade: string, curso: string): Resumo {
    return this.resumos().get(`${unidade}/${curso}`) ?? { documentos: 0, avisos: 0 };
  }
}
