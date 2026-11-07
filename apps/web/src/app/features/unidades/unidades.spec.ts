import { TestBed } from '@angular/core/testing';

import { configurar, responder } from '../../testes/configurar';
import { UNIDADES, aviso, versao } from '../../testes/dados';
import { Unidades } from './unidades';

describe('Unidades', () => {
  it('lista unidades e cursos com a situação de cada um', async () => {
    const http = configurar();
    const fixture = TestBed.createComponent(Unidades);
    fixture.detectChanges();
    responder(http, '/unidades', UNIDADES);
    expect(
      responder(http, '/ppcs', [versao(), versao({ sha256: 'b'.repeat(64) })]).get('limite'),
    ).toBe('200');
    responder(http, '/avisos', [aviso()]);
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect([...el.querySelectorAll('section.cartao h2')].map((h) => h.textContent)).toEqual([
      'Fatec Pompeia',
      'Fatec Marília',
    ]);
    const itens = [...el.querySelectorAll('.lista-cursos li')].map((li) => li.textContent ?? '');
    expect(itens[0]).toContain('nenhum documento');
    expect(itens[0]).toContain('precisa de ação');
    expect(itens[2]).toContain('2 documentos');
    expect(itens[2]).toContain('12/10/2026');
    expect(el.querySelector('.aviso')).not.toBeNull();
    http.verify();
  });

  it('explica quando a API está fora do ar', async () => {
    const http = configurar();
    const fixture = TestBed.createComponent(Unidades);
    fixture.detectChanges();
    http
      .expectOne('/api/unidades')
      .error(new ProgressEvent('error'), { status: 0, statusText: 'Unknown Error' });
    http.match(() => true).forEach((r) => r.flush([]));
    await fixture.whenStable();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('[role=alert]')?.textContent,
    ).toContain('Não foi possível falar com a API');
  });
});
