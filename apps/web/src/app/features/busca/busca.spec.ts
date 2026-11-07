import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { configurar, responder } from '../../testes/configurar';
import { UNIDADES, versao } from '../../testes/dados';
import { Busca } from './busca';

describe('Busca', () => {
  /** Monta a tela e responde /unidades. Quem chama responde /busca antes do whenStable. */
  function montar(q?: string) {
    const http = configurar();
    const fixture = TestBed.createComponent(Busca);
    if (q) fixture.componentRef.setInput('q', q);
    fixture.detectChanges();
    responder(http, '/unidades', UNIDADES);
    return { http, fixture, el: fixture.nativeElement as HTMLElement };
  }

  it('não busca com menos de 2 letras', async () => {
    const { http, fixture, el } = montar('a');
    await fixture.whenStable();
    http.expectNone((r) => r.url === '/api/busca');
    expect(el.textContent).toContain('Digite ao menos 2 letras');
  });

  it('mostra os trechos com o termo destacado, como texto', async () => {
    const { http, fixture, el } = montar('estagio');
    const params = responder(http, '/busca', [
      {
        versao: versao({ curso_nome: 'CST em Alimentos' }),
        relevancia: 0.5,
        trechos: [
          { texto: 'O ', destaque: false },
          { texto: 'Estágio', destaque: true },
          { texto: ' é <b>obrigatório</b>', destaque: false },
        ],
      },
    ]);
    expect(params.get('q')).toBe('estagio');
    await fixture.whenStable();
    expect(el.textContent).toContain('1 documento encontrado');
    expect(el.querySelector('mark')?.textContent).toBe('Estágio');
    expect(el.querySelector('.trecho')?.textContent).toBe('O Estágio é <b>obrigatório</b>');
    expect(el.querySelector('.trecho b')).toBeNull(); // A-8: nada de HTML vindo da API
    expect(el.querySelector('h2 a')?.getAttribute('href')).toBe(
      '/unidades/marilia/cursos/alimentos',
    );
  });

  it('manda os filtros para a API', async () => {
    const http = configurar();
    const fixture = TestBed.createComponent(Busca);
    fixture.componentRef.setInput('q', 'tcc');
    fixture.componentRef.setInput('tipo', 'ppc');
    fixture.componentRef.setInput('unidade', 'pompeia');
    fixture.detectChanges();
    responder(http, '/unidades', UNIDADES);
    const params = responder(http, '/busca', []);
    expect([params.get('tipo'), params.get('unidade')]).toEqual(['ppc', 'pompeia']);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Nada encontrado');
  });

  it('leva o texto digitado para a URL depois de uma pausa', async () => {
    const { fixture, el } = montar();
    await fixture.whenStable();
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const campo = el.querySelector<HTMLInputElement>('input[type=search]')!;
    campo.value = 'gestao';
    campo.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(navegar).not.toHaveBeenCalled(); // ainda dentro da pausa
    await new Promise((r) => setTimeout(r, 400));
    expect(navegar).toHaveBeenCalledWith(
      [],
      expect.objectContaining({ queryParams: { q: 'gestao' } }),
    );
  });
});
