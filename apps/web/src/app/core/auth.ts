import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, firstValueFrom, map, of, shareReplay, tap } from 'rxjs';

import { API_URL } from '../api/api';
import { SessaoAberta, Usuario } from '../api/tipos';

/**
 * Sessão de login. O token de acesso fica só na memória (nunca em `localStorage`); o refresh
 * token é um cookie HttpOnly que o JavaScript não enxerga. Ao recarregar a página, `restaurar`
 * troca o cookie por um novo token de acesso.
 */
@Injectable({ providedIn: 'root' })
export class Auth {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_URL);
  private readonly sessao = signal<SessaoAberta | null>(null);
  private renovando?: Observable<SessaoAberta | null>;
  private restaurando?: Promise<void>;

  readonly usuario = computed<Usuario | null>(() => this.sessao()?.usuario ?? null);
  readonly podeEnviar = computed(() => {
    const perfil = this.usuario()?.perfil;
    return perfil === 'coordenador' || perfil === 'admin_polo';
  });

  get token(): string | null {
    return this.sessao()?.access_token ?? null;
  }

  entrar(email: string, senha: string): Observable<Usuario> {
    return this.http.post<SessaoAberta>(`${this.base}/auth/login`, { email, senha }).pipe(
      tap((s) => this.sessao.set(s)),
      map((s) => s.usuario),
    );
  }

  /** A sessão local termina mesmo que a API esteja fora do ar. */
  sair(): Observable<void> {
    return this.http.post<void>(`${this.base}/auth/logout`, null).pipe(
      catchError(() => of(undefined)),
      finalize(() => this.sessao.set(null)),
    );
  }

  /** Pede um token novo. Chamadas simultâneas dividem a mesma requisição. */
  renovar(): Observable<SessaoAberta | null> {
    this.renovando ??= this.http.post<SessaoAberta | null>(`${this.base}/auth/refresh`, null).pipe(
      tap((s) => this.sessao.set(s)), // 204 (visitante) chega como null
      catchError((erro: unknown) => {
        if (erro instanceof HttpErrorResponse && erro.status === 401) {
          this.sessao.set(null);
        }
        return of(null);
      }),
      finalize(() => (this.renovando = undefined)),
      shareReplay(1),
    );
    return this.renovando;
  }

  /** Recupera a sessão uma vez por carga da página. A guarda de rota espera por isto. */
  restaurar(): Promise<void> {
    this.restaurando ??= firstValueFrom(this.renovar()).then(() => undefined);
    return this.restaurando;
  }
}
