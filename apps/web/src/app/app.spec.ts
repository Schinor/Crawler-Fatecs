import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { sessaoDeTeste } from './testes/dados';
import { Perfil } from './api/tipos';

describe('App', () => {
  async function montar(perfil?: Perfil) {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(App);
    const req = TestBed.inject(HttpTestingController).expectOne('/api/auth/refresh');
    if (perfil) {
      req.flush(sessaoDeTeste({ perfil }));
    } else {
      req.flush(null, { status: 204, statusText: 'No Content' });
    }
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const itens = [...el.querySelectorAll('nav a, nav button')].map((a) => a.textContent?.trim());
    return { el, itens };
  }

  it('visitante vê a navegação pública, Entrar e o link para pular ao conteúdo', async () => {
    const { el, itens } = await montar();
    expect(itens).toEqual(['Unidades', 'Buscar', 'Documentos', 'Entrar']);
    expect(el.querySelector('a.pular')?.getAttribute('href')).toBe('#conteudo');
  });

  it('quem pode enviar vê Enviar e Sair', async () => {
    const { el, itens } = await montar('coordenador');
    expect(itens).toEqual(['Unidades', 'Buscar', 'Documentos', 'Enviar', 'Sair']);
    expect(el.querySelector('nav button')?.getAttribute('aria-label')).toContain('Pessoa de Teste');
  });

  it('perfil consulta não vê Enviar', async () => {
    const { itens } = await montar('consulta');
    expect(itens).toEqual(['Unidades', 'Buscar', 'Documentos', 'Sair']);
  });
});
