import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { TIPOS_DOCUMENTO, TipoDocumento, Unidade, Versao } from '../../api/tipos';
import { RotuloTipoPipe, TamanhoPipe } from '../../shared/formatos';

/** Normaliza para a busca ignorar acentos e maiúsculas ("Ementário" acha "ementario"). */
export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}

/**
 * Todos os documentos, com filtro por unidade, tipo e texto (nome do curso ou título).
 * A busca no conteúdo dos PPCs (full-text) ainda não existe na API: o filtro é feito aqui.
 */
@Component({
  selector: 'app-documentos',
  imports: [DatePipe, RouterLink, RotuloTipoPipe, TamanhoPipe],
  templateUrl: './documentos.html',
})
export class Documentos {
  protected readonly api = inject(Api);
  protected readonly tipos = TIPOS_DOCUMENTO;

  protected readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });
  protected readonly versoes = httpResource<Versao[]>(
    () => ({ url: this.api.url('/ppcs'), params: { limite: 200 } }),
    { defaultValue: [] },
  );

  protected readonly texto = signal('');
  protected readonly unidade = signal('');
  protected readonly tipo = signal<TipoDocumento | ''>('');

  protected readonly filtradas = computed(() => {
    const termo = normalizar(this.texto().trim());
    return this.versoes
      .value()
      .filter((v) => !this.unidade() || v.unidade === this.unidade())
      .filter((v) => !this.tipo() || v.tipo_documento === this.tipo())
      .filter((v) => !termo || normalizar(`${v.curso_nome} ${v.titulo}`).includes(termo));
  });

  protected readonly nomesUnidades = computed(
    () => new Map(this.unidades.value().map((u) => [u.slug, u.nome])),
  );

  protected readonly erro = computed(() => {
    const e = this.versoes.error() ?? this.unidades.error();
    return e ? mensagemDeErro(e) : null;
  });

  protected valor(evento: Event): string {
    return (evento.target as HTMLInputElement | HTMLSelectElement).value;
  }

  protected limpar(): void {
    this.texto.set('');
    this.unidade.set('');
    this.tipo.set('');
  }
}
