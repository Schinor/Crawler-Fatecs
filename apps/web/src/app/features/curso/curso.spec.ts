import { TestBed } from '@angular/core/testing';

import { configurar, responder } from '../../testes/configurar';
import { UNIDADES, versao } from '../../testes/dados';
import { Curso } from './curso';

describe('Curso', () => {
  it('mostra o histórico por tipo e marca a versão atual de cada documento', async () => {
    const http = configurar();
    const fixture = TestBed.createComponent(Curso);
    fixture.componentRef.setInput('unidade', 'marilia');
    fixture.componentRef.setInput('curso', 'alimentos');
    fixture.detectChanges();

    responder(http, '/unidades', UNIDADES);
    const params = responder(http, '/ppcs', [
      versao({ sha256: '1'.repeat(64), coletado_em: '2026-01-10T03:00:00Z' }),
      versao({ sha256: '2'.repeat(64), coletado_em: '2026-10-12T03:00:00Z', origem: 'upload' }),
      versao({
        sha256: '3'.repeat(64),
        tipo_documento: 'ementario',
        precisa_ocr: true,
        links: { arquivo: '/x', texto: null },
      }),
    ]);
    expect(params.get('unidade')).toBe('marilia');
    expect(params.get('curso')).toBe('alimentos');
    responder(http, '/avisos', []);
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toBe('CST em Alimentos');
    const grupos = [...el.querySelectorAll('section.cartao')];
    expect(grupos.map((g) => g.querySelector('h2')?.textContent)).toEqual([
      expect.stringContaining('Matriz curricular'),
      expect.stringContaining('Ementário'),
    ]);
    const matriz = grupos[0].querySelectorAll('.linha-do-tempo li');
    expect(matriz).toHaveLength(2);
    expect(matriz[0].textContent).toContain('versão atual');
    expect(matriz[0].textContent).toContain('Enviado manualmente');
    expect(matriz[1].textContent).toContain('versão anterior');
    expect(grupos[1].textContent).not.toContain('versão atual'); // documento com uma versão só
    expect(matriz[0].querySelector('a[download]')?.getAttribute('href')).toBe(
      `/api/ppcs/marilia/alimentos/${'2'.repeat(64)}/arquivo`,
    );
    expect(grupos[1].textContent).toContain('sem texto (imagem)');
    expect(grupos[1].textContent).not.toContain('Ver texto extraído');
    http.verify();
  });
});
