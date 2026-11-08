import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';

import { Api, mensagemDeErro } from '../../api/api';
import { ResultadoBusca, TIPOS_DOCUMENTO, TipoDocumento, Unidade } from '../../api/tipos';
import { RotuloTipoPipe } from '../../shared/formatos';

const MINIMO = 2; // a API exige ao menos 2 caracteres

/**
 * Busca no conteúdo dos documentos (full-text em português, sem acento). A consulta fica na URL
 * (`/busca?q=...`), então dá para compartilhar o link de uma busca.
 */
@Component({
  selector: 'app-busca',
  imports: [DatePipe, RouterLink, RotuloTipoPipe],
  templateUrl: './busca.html',
})
export class Busca implements OnInit {
  /** Vêm da query string (withComponentInputBinding). */
  readonly q = input<string>();
  readonly tipo = input<string>();
  readonly unidade = input<string>();

  private readonly router = inject(Router);
  protected readonly api = inject(Api);
  protected readonly tipos = TIPOS_DOCUMENTO;

  /** O que está no campo; vai para a URL 300 ms depois da última tecla. */
  protected readonly digitado = signal('');

  protected readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });

  protected readonly consulta = computed(() => (this.q() ?? '').trim());
  protected readonly resultados = httpResource<ResultadoBusca[]>(
    () => {
      if (this.consulta().length < MINIMO) return undefined;
      const params: Record<string, string> = { q: this.consulta(), limite: '30' };
      const tipo = this.tipo();
      const unidade = this.unidade();
      if (tipo) params['tipo'] = tipo;
      if (unidade) params['unidade'] = unidade;
      return { url: this.api.url('/busca'), params };
    },
    { defaultValue: [] },
  );

  protected readonly nomesUnidades = computed(
    () => new Map(this.unidades.value().map((u) => [u.slug, u.nome])),
  );
  protected readonly erro = computed(() => {
    const e = this.resultados.error();
    return e ? mensagemDeErro(e) : null;
  });

  constructor() {
    toObservable(this.digitado)
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((texto) => {
        if (texto.trim() !== this.consulta()) this.atualizar({ q: texto.trim() || null });
      });
  }

  ngOnInit(): void {
    this.digitado.set(this.q() ?? '');
  }

  protected valor(evento: Event): string {
    return (evento.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected buscarAgora(): void {
    this.atualizar({ q: this.digitado().trim() || null });
  }

  protected atualizar(params: {
    q?: string | null;
    tipo?: string | null;
    unidade?: string | null;
  }) {
    void this.router.navigate([], {
      queryParams: params,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  protected filtroTipo(evento: Event): void {
    this.atualizar({ tipo: (this.valor(evento) as TipoDocumento) || null });
  }

  protected filtroUnidade(evento: Event): void {
    this.atualizar({ unidade: this.valor(evento) || null });
  }
}
