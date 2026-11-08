import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, InjectionToken, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { TipoDocumento, Versao } from './tipos';

/**
 * Endereço da API. No desenvolvimento, o `ng serve` repassa `/api` para o uvicorn
 * (proxy.conf.json); em produção, o proxy reverso faz o mesmo. Assim não há CORS.
 */
export const API_URL = new InjectionToken<string>('API_URL', { factory: () => '/api' });

export interface Envio {
  unidade: string;
  curso: string;
  tipo_documento: TipoDocumento;
  titulo: string;
  arquivo: File;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_URL);

  /** Caminho da API (`/ppcs`) ou link devolvido por ela (`links.arquivo`) → URL completa. */
  url(caminho: string): string {
    return `${this.base}${caminho}`;
  }

  /** Upload manual. O interceptor de autenticação acrescenta o token da sessão. */
  enviar(envio: Envio): Observable<Versao> {
    const corpo = new FormData();
    corpo.set('unidade', envio.unidade);
    corpo.set('curso', envio.curso);
    corpo.set('tipo_documento', envio.tipo_documento);
    corpo.set('titulo', envio.titulo);
    corpo.set('arquivo', envio.arquivo, envio.arquivo.name);
    return this.http.post<Versao>(this.url('/ppcs'), corpo);
  }
}

/** Mensagem para a pessoa a partir de um erro HTTP (a API responde `{"detail": "..."}`). */
export function mensagemDeErro(erro: unknown): string {
  if (!(erro instanceof HttpErrorResponse)) {
    return 'Algo deu errado. Tente de novo.';
  }
  if (erro.status === 0) {
    return 'Não foi possível falar com a API. Ela está rodando?';
  }
  const detalhe: unknown = erro.error?.detail;
  if (typeof detalhe === 'string') {
    return detalhe.charAt(0).toUpperCase() + detalhe.slice(1) + '.';
  }
  if (erro.status === 422) {
    return 'Dados inválidos. Confira os campos.';
  }
  return `A API respondeu com erro ${erro.status}.`;
}
