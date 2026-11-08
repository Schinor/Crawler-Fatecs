import { TestBed } from '@angular/core/testing';

import { Coleta } from '../../api/tipos';
import { configurar, responder } from '../../testes/configurar';
import { UNIDADES } from '../../testes/dados';
import { Coletas } from './coletas';

function coleta(parcial: Partial<Coleta>): Coleta {
  return {
    unidade_slug: 'pompeia',
    curso_slug: 'big-data',
    curso_nome: 'CST em Big Data',
    iniciada_em: '2026-11-08T03:00:00Z',
    status: 'sem_mudanca',
    detalhe: {},
    ...parcial,
  };
}

describe('Coletas', () => {
  async function montar(coletas: Coleta[]) {
    const http = configurar();
    const fixture = TestBed.createComponent(Coletas);
    fixture.detectChanges();
    responder(http, '/coletas', coletas);
    responder(http, '/unidades', UNIDADES);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    return { fixture, el, linhas: () => [...el.querySelectorAll('tbody tr')] };
  }

  const RODADA = [
    coleta({ status: 'novo_ppc' }),
    coleta({ status: 'sem_mudanca' }),
    coleta({ status: 'sem_mudanca' }),
    coleta({
      curso_slug: 'sistemas-inteligentes',
      curso_nome: 'CST em Sistemas Inteligentes',
      status: 'erro_drive',
      detalhe: { erro: 'bloqueado pelo robots.txt <b>' },
    }),
  ];

  it('mostra uma linha por curso, somando os resultados', async () => {
    const { el, linhas } = await montar(RODADA);
    expect(linhas().length).toBe(2);
    const selos = [...linhas()[0].querySelectorAll('.selo')].map((s) =>
      s.textContent?.replace(/\s+/g, ' ').trim(),
    );
    expect(selos).toEqual(['Documento novo', 'Sem mudança (2)']);
    expect(linhas()[0].querySelector('a')?.getAttribute('href')).toBe(
      '/unidades/pompeia/cursos/big-data',
    );
    expect(el.textContent).toContain('1 de 2');
  });

  it('exibe o erro como texto e filtra os cursos com problema', async () => {
    const { fixture, el, linhas } = await montar(RODADA);
    expect(el.querySelector('tbody b')).toBeNull();
    expect(linhas()[1].textContent).toContain('bloqueado pelo robots.txt <b>');
    const caixa = el.querySelector<HTMLInputElement>('input[type=checkbox]')!;
    caixa.checked = true;
    caixa.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(linhas().length).toBe(1);
    expect(linhas()[0].textContent).toContain('Sistemas Inteligentes');
  });

  it('falha na página inicial aparece sem link de curso', async () => {
    const { linhas } = await montar([
      coleta({ curso_slug: '-', curso_nome: '-', status: 'erro_http' }),
    ]);
    expect(linhas()[0].textContent).toContain('Página inicial da unidade');
    expect(linhas()[0].querySelector('a')).toBeNull();
  });

  it('avisa quando ainda não há coletas', async () => {
    const { el } = await montar([]);
    expect(el.textContent).toContain('Nenhuma coleta gravada');
  });
});
