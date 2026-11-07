import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import localePt from '@angular/common/locales/pt';
import { LOCALE_ID, Provider } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

registerLocaleData(localePt);

export function configurar(...extras: Provider[]): HttpTestingController {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      { provide: LOCALE_ID, useValue: 'pt-BR' },
      ...extras,
    ],
  });
  return TestBed.inject(HttpTestingController);
}

/** Responde uma requisição GET pelo caminho (sem a query) e devolve os parâmetros usados. */
export function responder(
  http: HttpTestingController,
  caminho: string,
  corpo: Parameters<TestRequest['flush']>[0],
) {
  const req = http.expectOne((r) => r.method === 'GET' && r.url === `/api${caminho}`);
  req.flush(corpo);
  return req.request.params;
}
