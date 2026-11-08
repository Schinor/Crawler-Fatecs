import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, UrlTree } from '@angular/router';
import type { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { sessaoDeTeste } from '../testes/dados';
import { Auth } from './auth';
import { exigirAdmin, exigirEnvio } from './auth.guard';
import { autenticar } from './auth.interceptor';

describe('sessão de login', () => {
  function preparar() {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([autenticar])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    return {
      http: TestBed.inject(HttpTestingController),
      cliente: TestBed.inject(HttpClient),
      auth: TestBed.inject(Auth),
    };
  }

  const NAO_AUTORIZADO = { status: 401, statusText: 'Unauthorized' };

  function logar(http: HttpTestingController, auth: Auth, token = 'token-1') {
    auth.entrar('p@teste.invalid', 'senha').subscribe();
    http.expectOne('/api/auth/login').flush(sessaoDeTeste({}, token));
  }

  it('manda o token só para a API', () => {
    const { http, cliente, auth } = preparar();
    logar(http, auth);
    cliente.get('/api/ppcs').subscribe();
    cliente.get('https://outro-site.invalid/api/x').subscribe();
    expect(http.expectOne('/api/ppcs').request.headers.get('Authorization')).toBe('Bearer token-1');
    expect(
      http.expectOne('https://outro-site.invalid/api/x').request.headers.has('Authorization'),
    ).toBe(false);
  });

  it('visitante não manda cabeçalho', () => {
    const { http, cliente } = preparar();
    cliente.get('/api/ppcs').subscribe();
    expect(http.expectOne('/api/ppcs').request.headers.has('Authorization')).toBe(false);
  });

  it('token vencido: renova uma vez e repete a requisição', () => {
    const { http, cliente, auth } = preparar();
    logar(http, auth);
    let resposta: unknown;
    cliente.post('/api/ppcs', null).subscribe((r) => (resposta = r));
    http.expectOne('/api/ppcs').flush({ detail: 'x' }, NAO_AUTORIZADO);
    http.expectOne('/api/auth/refresh').flush(sessaoDeTeste({}, 'token-2'));
    const repetida = http.expectOne('/api/ppcs');
    expect(repetida.request.headers.get('Authorization')).toBe('Bearer token-2');
    repetida.flush({ ok: true });
    expect(resposta).toEqual({ ok: true });
  });

  it('duas requisições vencidas dividem uma renovação só', () => {
    const { http, cliente, auth } = preparar();
    logar(http, auth);
    cliente.get('/api/a').subscribe();
    cliente.get('/api/b').subscribe();
    http.expectOne('/api/a').flush({}, NAO_AUTORIZADO);
    http.expectOne('/api/b').flush({}, NAO_AUTORIZADO);
    http.expectOne('/api/auth/refresh').flush(sessaoDeTeste({}, 'token-2'));
    http.expectOne('/api/a');
    http.expectOne('/api/b');
  });

  it('refresh recusado encerra a sessão e devolve o erro original', () => {
    const { http, cliente, auth } = preparar();
    logar(http, auth);
    let status = 0;
    cliente.post('/api/ppcs', null).subscribe({ error: (e) => (status = e.status) });
    http.expectOne('/api/ppcs').flush({}, NAO_AUTORIZADO);
    http.expectOne('/api/auth/refresh').flush({}, NAO_AUTORIZADO);
    expect(status).toBe(401);
    expect(auth.usuario()).toBeNull();
    http.expectNone('/api/ppcs');
  });

  it('API fora do ar no refresh não derruba a sessão', () => {
    const { http, auth } = preparar();
    logar(http, auth);
    auth.renovar().subscribe();
    http.expectOne('/api/auth/refresh').error(new ProgressEvent('error'));
    expect(auth.usuario()).not.toBeNull();
  });

  it('sair limpa a sessão mesmo com erro na API', async () => {
    const { http, auth } = preparar();
    logar(http, auth);
    const saida = firstValueFrom(auth.sair());
    http.expectOne('/api/auth/logout').error(new ProgressEvent('error'));
    await saida;
    expect(auth.usuario()).toBeNull();
    expect(auth.token).toBeNull();
  });

  async function guarda(url: string) {
    return TestBed.runInInjectionContext(() =>
      exigirEnvio({} as ActivatedRouteSnapshot, { url } as RouterStateSnapshot),
    ) as Promise<boolean | UrlTree>;
  }

  it('guarda: visitante vai para o login e volta depois', async () => {
    const { http } = preparar();
    const resultado = guarda('/enviar?unidade=pompeia');
    http.expectOne('/api/auth/refresh').flush(null, { status: 204, statusText: 'No Content' });
    const url = TestBed.inject(Router).serializeUrl((await resultado) as UrlTree);
    expect(url).toBe('/entrar?voltar=%2Fenviar%3Funidade%3Dpompeia');
  });

  it('guarda: a sessão restaurada pelo cookie libera a tela', async () => {
    const { http } = preparar();
    const resultado = guarda('/enviar');
    http.expectOne('/api/auth/refresh').flush(sessaoDeTeste());
    expect(await resultado).toBe(true);
  });

  it('guarda: Coletas é só do admin do polo', async () => {
    const { http } = preparar();
    const resultado = TestBed.runInInjectionContext(() =>
      exigirAdmin({} as ActivatedRouteSnapshot, { url: '/admin/coletas' } as RouterStateSnapshot),
    ) as Promise<boolean | UrlTree>;
    http.expectOne('/api/auth/refresh').flush(sessaoDeTeste({ perfil: 'coordenador' }));
    expect(await resultado).toBeInstanceOf(UrlTree);
  });

  it('guarda: perfil consulta não entra', async () => {
    const { http } = preparar();
    const resultado = guarda('/enviar');
    http.expectOne('/api/auth/refresh').flush(sessaoDeTeste({ perfil: 'consulta' }));
    expect(await resultado).toBeInstanceOf(UrlTree);
  });
});
