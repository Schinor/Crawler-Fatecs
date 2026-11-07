import { versao } from '../testes/dados';
import { agruparPorTipo, tamanho } from './formatos';

describe('formatos', () => {
  it('agrupa por tipo na ordem PPC, matriz, ementário', () => {
    const grupos = agruparPorTipo([
      versao({ sha256: '1'.repeat(64), tipo_documento: 'ementario' }),
      versao({ sha256: '4'.repeat(64), tipo_documento: 'ppc' }),
      versao({ sha256: '2'.repeat(64) }),
    ]);
    expect(grupos.map((g) => g.tipo)).toEqual(['ppc', 'matriz', 'ementario']);
  });

  it('separa documentos publicados juntos e junta as versões do mesmo link', () => {
    const grade = (letra: string) => `https://cps.blob/${letra}31.pdf`;
    const [matriz] = agruparPorTipo([
      versao({ sha256: '1'.repeat(64), arquivo_url: grade('A') }),
      versao({ sha256: '2'.repeat(64), arquivo_url: grade('B') }),
      versao({
        sha256: '3'.repeat(64),
        arquivo_url: grade('A'),
        coletado_em: '2026-11-08T03:00:00Z',
      }),
      versao({ sha256: '4'.repeat(64), arquivo_url: null, origem: 'upload' }),
    ]);
    expect(matriz.documentos.map((d) => d.versoes.map((v) => v.sha256[0]))).toEqual([
      ['3', '1'], // mesmo link, conteúdo novo: a versão de novembro é a atual
      ['2'],
      ['4'],
    ]);
  });

  it('formata tamanhos', () => {
    expect(tamanho(512)).toBe('512 B');
    expect(tamanho(250_000)).toBe('244 KB');
    expect(tamanho(3.5 * 1024 * 1024)).toBe('3,5 MB');
  });
});
