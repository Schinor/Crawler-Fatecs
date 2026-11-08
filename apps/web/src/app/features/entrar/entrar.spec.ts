import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { vi } from 'vitest';

import { configurar } from '../../testes/configurar';
import { sessaoDeTeste } from '../../testes/dados';
import { Entrar } from './entrar';

describe('Entrar', () => {
  function montar(voltar?: string) {
    const http = configurar({
      provide: ActivatedRoute,
      useValue: { snapshot: { queryParamMap: convertToParamMap(voltar ? { voltar } : {}) } },
    });
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Entrar);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const digitar = (seletor: string, valor: string) => {
      const input = el.querySelector<HTMLInputElement>(seletor)!;
      input.value = valor;
      input.dispatchEvent(new Event('input'));
    };
    const enviar = () => el.querySelector('form')!.dispatchEvent(new Event('submit'));
    return { http, fixture, el, navegar, digitar, enviar };
  }

  async function logar(voltar?: string) {
    const t = montar(voltar);
    t.digitar('input[type=email]', 'pessoa@teste.invalid');
    t.digitar('input[type=password]', 'senha-de-teste');
    t.enviar();
    const req = t.http.expectOne('/api/auth/login');
    expect(req.request.body).toEqual({ email: 'pessoa@teste.invalid', senha: 'senha-de-teste' });
    return { ...t, req };
  }

  it('não chama a API sem e-mail e senha', async () => {
    const { http, fixture, el, enviar } = montar();
    enviar();
    await fixture.whenStable();
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Preencha');
    http.expectNone('/api/auth/login');
  });

  it('volta para a página que pediu o login', async () => {
    const { req, navegar } = await logar('/enviar?unidade=pompeia');
    req.flush(sessaoDeTeste());
    expect(navegar).toHaveBeenCalledWith('/enviar?unidade=pompeia');
  });

  it('ignora destino fora do site', async () => {
    const { req, navegar } = await logar('//site-falso.invalid');
    req.flush(sessaoDeTeste());
    expect(navegar).toHaveBeenCalledWith('/');
  });

  it('mostra o erro da API e limpa a senha', async () => {
    const { req, fixture, el } = await logar();
    req.flush(
      { detail: 'e-mail ou senha incorretos' },
      { status: 401, statusText: 'Unauthorized' },
    );
    await fixture.whenStable();
    expect(el.querySelector('[role=alert]')?.textContent).toContain('E-mail ou senha incorretos.');
    expect(el.querySelector<HTMLInputElement>('input[type=password]')!.value).toBe('');
  });

  it('avisa quando a conta logada não pode enviar', async () => {
    const { req, fixture, el } = await logar();
    req.flush(sessaoDeTeste({ perfil: 'consulta' }));
    await fixture.whenStable();
    expect(el.textContent).toContain('só consulta documentos');
    expect(el.querySelector('form')).toBeNull();
  });
});
