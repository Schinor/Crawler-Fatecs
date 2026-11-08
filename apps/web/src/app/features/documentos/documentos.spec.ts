import { TestBed } from '@angular/core/testing';

import { configurar, responder } from '../../testes/configurar';
import { UNIDADES, versao } from '../../testes/dados';
import { Documentos, normalizar } from './documentos';

describe('Documentos', () => {
  async function montar() {
    const http = configurar();
    const fixture = TestBed.createComponent(Documentos);
    fixture.detectChanges();
    responder(http, '/unidades', UNIDADES);
    responder(http, '/ppcs', [
      versao({ sha256: '1'.repeat(64) }),
      versao({ sha256: '2'.repeat(64), tipo_documento: 'ementario', titulo: 'Ementário 2024' }),
      versao({
        sha256: '3'.repeat(64),
        unidade: 'pompeia',
        curso: 'big-data',
        tipo_documento: 'ppc',
        curso_nome: 'CST em Big Data no Agronegócio',
        origem: 'upload',
        titulo: 'PPC',
      }),
    ]);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const linhas = () => el.querySelectorAll('tbody tr');
    const mudar = async (seletor: string, valor: string, evento: string) => {
      const campo = el.querySelector<HTMLInputElement | HTMLSelectElement>(seletor)!;
      campo.value = valor;
      campo.dispatchEvent(new Event(evento));
      await fixture.whenStable();
    };
    return { el, linhas, mudar };
  }

  it('ignora acentos e maiúsculas na busca', () => {
    expect(normalizar('Ementário AGRONEGÓCIO')).toBe('ementario agronegocio');
  });

  it('filtra por texto, unidade e tipo', async () => {
    const { el, linhas, mudar } = await montar();
    expect(linhas()).toHaveLength(3);

    await mudar('input[type=search]', 'agronegocio', 'input');
    expect(linhas()).toHaveLength(1);
    expect(linhas()[0].textContent).toContain('Big Data');

    await mudar('input[type=search]', '', 'input');
    await mudar('select', 'marilia', 'change');
    expect(linhas()).toHaveLength(2);

    await mudar('label:nth-of-type(3) select', 'ementario', 'change');
    expect(linhas()).toHaveLength(1);
    expect(el.textContent).toContain('1 de 3 documentos');
  });

  it('avisa quando nada combina com os filtros', async () => {
    const { linhas, mudar } = await montar();
    await mudar('input[type=search]', 'xyz', 'input');
    expect(linhas()[0].textContent).toContain('Nenhum documento com esses filtros');
  });
});
