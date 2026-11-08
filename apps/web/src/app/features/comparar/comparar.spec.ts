import { TestBed } from '@angular/core/testing';

import { Comparacao } from '../../api/tipos';
import { configurar, responder } from '../../testes/configurar';
import { versao } from '../../testes/dados';
import { Comparar, previa } from './comparar';

const ANTIGA = versao({ sha256: '1'.repeat(64), coletado_em: '2026-01-10T03:00:00Z' });
const NOVA = versao({ sha256: '2'.repeat(64) });
const SEM_TEXTO = versao({
  sha256: '3'.repeat(64),
  formato: 'zip',
  links: { arquivo: '/x', texto: null },
});
const LONGO = 'Parágrafo igual. '.repeat(40);

const RESPOSTA: Comparacao = {
  de: ANTIGA,
  para: NOVA,
  palavras_adicionadas: 1,
  palavras_removidas: 1,
  semelhanca: 0.95,
  blocos: [
    { tipo: 'igual', trechos: [{ tipo: 'igual', texto: LONGO }] },
    {
      tipo: 'alterado',
      trechos: [
        { tipo: 'igual', texto: 'Carga horária total:' },
        { tipo: 'removido', texto: '2400' },
        { tipo: 'adicionado', texto: '2800' },
        { tipo: 'igual', texto: 'horas.' },
      ],
    },
  ],
};

describe('Comparar', () => {
  /** Responde a lista de versões; a comparação (se houver) fica para quem chama. */
  function montar(de?: string, para?: string) {
    const http = configurar();
    const fixture = TestBed.createComponent(Comparar);
    fixture.componentRef.setInput('unidade', 'marilia');
    fixture.componentRef.setInput('curso', 'alimentos');
    if (de) fixture.componentRef.setInput('de', de);
    if (para) fixture.componentRef.setInput('para', para);
    fixture.detectChanges();
    responder(http, '/ppcs', [NOVA, ANTIGA, SEM_TEXTO]);
    return { http, fixture, el: fixture.nativeElement as HTMLElement };
  }

  it('só oferece versões com texto', async () => {
    const { fixture, el } = montar();
    await fixture.whenStable();
    const opcoes = el.querySelectorAll('select')[0].querySelectorAll('option');
    expect(opcoes).toHaveLength(3); // "Escolha" + 2 com texto
    expect(el.textContent).toContain('Escolha as duas versões');
  });

  it('mostra o resumo e as palavras trocadas, com o trecho igual recolhido', async () => {
    const { http, fixture, el } = montar(ANTIGA.sha256, NOVA.sha256);
    const params = responder(http, '/ppcs/marilia/alimentos/comparar', RESPOSTA);
    expect([params.get('de'), params.get('para')]).toEqual([ANTIGA.sha256, NOVA.sha256]);
    await fixture.whenStable();

    expect(el.querySelector('.resumo-diff')?.textContent).toContain('95% igual');
    expect(el.querySelector('del')?.textContent).toBe('2400');
    expect(el.querySelector('ins')?.textContent).toBe('2800');
    expect(el.querySelector('.alterado')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'Carga horária total: 2400 2800 horas.',
    );
    expect(el.querySelector('details summary')?.textContent).toBe('80 palavras sem mudança');
  });

  it('não chama a API com a mesma versão dos dois lados', async () => {
    const { http, fixture, el } = montar(NOVA.sha256, NOVA.sha256);
    await fixture.whenStable();
    http.expectNone((r) => r.url.endsWith('/comparar'));
    expect(el.textContent).toContain('Escolha duas versões diferentes');
  });

  it('mostra trecho reescrito inteiro, antes e depois', async () => {
    const { http, fixture, el } = montar(ANTIGA.sha256, NOVA.sha256);
    responder(http, '/ppcs/marilia/alimentos/comparar', {
      ...RESPOSTA,
      blocos: [
        {
          tipo: 'alterado',
          trechos: [
            { tipo: 'removido', texto: 'Ementa antiga\nlinha 2' },
            { tipo: 'adicionado', texto: 'Ementa nova' },
          ],
        },
      ],
    });
    await fixture.whenStable();
    const lados = [...el.querySelectorAll('.lado')].map((l) => l.textContent?.trim());
    expect(lados).toEqual(['Antes Ementa antiga\nlinha 2', 'Depois Ementa nova']);
    const [de, para] = [...el.querySelectorAll('select')].map((s) => s.value);
    expect([de, para]).toEqual([ANTIGA.sha256, NOVA.sha256]); // as versões da URL ficam escolhidas
  });

  it('prévia recolhe só textos longos', () => {
    expect(previa('curto').recolhido).toBe(false);
    expect(previa(LONGO).recolhido).toBe(true);
  });
});
