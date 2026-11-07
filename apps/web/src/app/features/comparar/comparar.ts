import { DatePipe, DecimalPipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, input } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { BlocoDiff, Comparacao, Versao } from '../../api/tipos';
import { RotuloTipoPipe } from '../../shared/formatos';

const PREVIA = 160; // caracteres mostrados de cada lado de um trecho sem mudança

/** Resumo de um bloco sem mudança: começo e fim, com o meio recolhido. */
export function previa(texto: string): { inicio: string; fim: string; recolhido: boolean } {
  if (texto.length <= PREVIA * 2 + 40) return { inicio: texto, fim: '', recolhido: false };
  return { inicio: texto.slice(0, PREVIA), fim: texto.slice(-PREVIA), recolhido: true };
}

/**
 * Compara o texto de duas versões do mesmo curso. As versões ficam na URL
 * (`?de=<sha>&para=<sha>`), então dá para compartilhar o link de uma comparação.
 */
@Component({
  selector: 'app-comparar',
  imports: [DatePipe, DecimalPipe, RouterLink, RotuloTipoPipe],
  templateUrl: './comparar.html',
})
export class Comparar {
  readonly unidade = input.required<string>();
  readonly curso = input.required<string>();
  readonly de = input<string>();
  readonly para = input<string>();

  private readonly router = inject(Router);
  private readonly api = inject(Api);

  protected readonly versoes = httpResource<Versao[]>(
    () => ({
      url: this.api.url('/ppcs'),
      params: { unidade: this.unidade(), curso: this.curso(), limite: 200 },
    }),
    { defaultValue: [] },
  );
  /** Só versões com texto extraído podem ser comparadas. */
  protected readonly comparaveis = computed(() =>
    this.versoes.value().filter((v) => v.links.texto),
  );

  protected readonly comparacao = httpResource<Comparacao>(() => {
    const [de, para] = [this.de(), this.para()];
    if (!de || !para || de === para) return undefined;
    return {
      url: this.api.url(`/ppcs/${this.unidade()}/${this.curso()}/comparar`),
      params: { de, para },
    };
  });

  protected readonly cursoNome = computed(
    () => this.versoes.value()[0]?.curso_nome ?? this.curso(),
  );
  protected readonly erro = computed(() => {
    const e = this.versoes.error() ?? this.comparacao.error();
    return e ? mensagemDeErro(e) : null;
  });
  protected readonly mudancas = computed(
    () => this.comparacao.value()?.blocos.filter((b) => b.tipo === 'alterado').length ?? 0,
  );

  protected readonly previa = previa;

  protected escolher(lado: 'de' | 'para', evento: Event): void {
    const sha = (evento.target as HTMLSelectElement).value || null;
    void this.router.navigate([], {
      queryParams: { [lado]: sha },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  protected inverter(): void {
    void this.router.navigate([], {
      queryParams: { de: this.para(), para: this.de() },
      replaceUrl: true,
    });
  }

  protected rotulo(v: Versao): string {
    const data = new Date(v.coletado_em).toLocaleDateString('pt-BR');
    return `${data} · ${v.titulo || v.sha256.slice(0, 12)}`;
  }

  /** Trecho reescrito: só removido e adicionado, sem palavras em comum (mostrado lado a lado). */
  protected reescrito(bloco: BlocoDiff): boolean {
    return !bloco.trechos.some((t) => t.tipo === 'igual');
  }

  protected palavras(bloco: BlocoDiff): number {
    return bloco.trechos.reduce((n, t) => n + t.texto.split(/\s+/).filter(Boolean).length, 0);
  }
}
