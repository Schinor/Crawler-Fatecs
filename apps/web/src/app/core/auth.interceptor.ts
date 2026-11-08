import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { API_URL } from '../api/api';
import { Auth } from './auth';

/** Envia o token à API (e só a ela) e, se ele venceu, renova uma vez e repete a requisição. */
export const autenticar: HttpInterceptorFn = (req, next) => {
  const auth = inject(Auth);
  const base = inject(API_URL);
  if (!req.url.startsWith(`${base}/`) || req.url.startsWith(`${base}/auth/`)) {
    return next(req);
  }
  const comToken = (token: string | null): HttpRequest<unknown> =>
    token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(comToken(auth.token)).pipe(
    catchError((erro: unknown) => {
      if (!(erro instanceof HttpErrorResponse) || erro.status !== 401 || !auth.token) {
        return throwError(() => erro);
      }
      return auth
        .renovar()
        .pipe(
          switchMap((sessao) =>
            sessao ? next(comToken(sessao.access_token)) : throwError(() => erro),
          ),
        );
    }),
  );
};
