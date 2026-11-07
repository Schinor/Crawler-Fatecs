import { DatePipe } from '@angular/common';
import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Aviso } from '../api/tipos';
import { RotuloTipoPipe } from './formatos';

/**
 * Banner dos avisos abertos (ex.: PPC no Drive bloqueado pelo robots.txt).
 * Tudo que vem da API é exibido por interpolação: nunca `innerHTML` (docs/seguranca.md, A-8).
 */
@Component({
  selector: 'app-avisos-banner',
  imports: [DatePipe, RouterLink, RotuloTipoPipe],
  template: `
    @if (avisos().length) {
      <section class="aviso" role="status" aria-labelledby="avisos-titulo">
        <h2 id="avisos-titulo">
          {{
            avisos().length === 1 ? '1 documento precisa' : avisos().length + ' documentos precisam'
          }}
          de ação
        </h2>
        <ul>
          @for (a of avisos(); track a.arquivo_url) {
            <li>
              <strong>{{ a.curso_nome }}</strong> · {{ a.tipo_documento | rotuloTipo }}
              @if (a.titulo_link) {
                <span class="discreto">({{ a.titulo_link }})</span>
              }
              <p>{{ a.mensagem }}</p>
              <p class="discreto">
                Desde {{ a.detectado_em | date: 'dd/MM/yyyy' }} ·
                <a [href]="a.pagina_url" target="_blank" rel="noopener noreferrer"
                  >página do curso</a
                >
                ·
                <a [href]="a.arquivo_url" target="_blank" rel="noopener noreferrer"
                  >documento no Drive</a
                >
                ·
                <a
                  routerLink="/enviar"
                  [queryParams]="{
                    unidade: a.unidade_slug,
                    curso: a.curso_slug,
                    tipo: a.tipo_documento,
                  }"
                  >enviar o arquivo</a
                >
              </p>
            </li>
          }
        </ul>
      </section>
    }
  `,
})
export class AvisosBanner {
  readonly avisos = input.required<readonly Aviso[]>();
}
