import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';

import { configurar, responder } from '../../testes/configurar';
import { UNIDADES, versao } from '../../testes/dados';
import { Enviar } from './enviar';

describe('Enviar', () => {
  async function montar(query: Record<string, string> = {}) {
    const http = configurar({
      provide: ActivatedRoute,
      useValue: { snapshot: { queryParamMap: convertToParamMap(query) } },
    });
    const fixture = TestBed.createComponent(Enviar);
    fixture.detectChanges();
    responder(http, '/unidades', UNIDADES);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    return { http, fixture, el };
  }

  function escolherArquivo(el: HTMLElement) {
    const input = el.querySelector<HTMLInputElement>('input[type=file]')!;
    const arquivo = new File(['%PDF-1.7'], 'ppc.pdf', { type: 'application/pdf' });
    Object.defineProperty(input, 'files', { value: [arquivo] });
    input.dispatchEvent(new Event('change'));
  }

  function digitar(el: HTMLElement, seletor: string, valor: string) {
    const input = el.querySelector<HTMLInputElement>(seletor)!;
    input.value = valor;
    input.dispatchEvent(new Event('input'));
  }

  it('vem preenchido a partir do aviso (query string)', async () => {
    const { el } = await montar({ unidade: 'pompeia', curso: 'big-data', tipo: 'ppc' });
    const [unidade, curso, tipo] = [...el.querySelectorAll('select')].map((s) => s.value);
    expect([unidade, curso, tipo]).toEqual(['pompeia', 'big-data', 'ppc']);
  });

  it('não envia sem arquivo e token', async () => {
    const { http, fixture, el } = await montar({ unidade: 'pompeia', curso: 'big-data' });
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Preencha');
    http.expectNone('/api/ppcs');
  });

  it('envia multipart com o token no cabeçalho e mostra o resultado', async () => {
    const { http, fixture, el } = await montar({ unidade: 'pompeia', curso: 'big-data' });
    escolherArquivo(el);
    digitar(el, 'input[type=text]', 'PPC 2026');
    digitar(el, 'input[type=password]', 'token-de-teste');
    el.querySelector('form')!.dispatchEvent(new Event('submit'));

    const req = http.expectOne((r) => r.method === 'POST' && r.url === '/api/ppcs');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-de-teste');
    const corpo = req.request.body as FormData;
    expect(corpo.get('unidade')).toBe('pompeia');
    expect(corpo.get('curso')).toBe('big-data');
    expect(corpo.get('tipo_documento')).toBe('ppc');
    expect(corpo.get('titulo')).toBe('PPC 2026');
    expect((corpo.get('arquivo') as File).name).toBe('ppc.pdf');
    req.flush(
      versao({
        unidade: 'pompeia',
        curso: 'big-data',
        curso_nome: 'CST em Big Data',
        titulo: 'PPC 2026',
      }),
      {
        status: 201,
        statusText: 'Created',
      },
    );
    await fixture.whenStable();
    expect(el.querySelector('.sucesso')?.textContent).toContain('Documento recebido');
    expect(el.querySelector('.sucesso a')?.getAttribute('href')).toBe(
      '/unidades/pompeia/cursos/big-data',
    );
  });

  it('mostra a mensagem da API quando a versão já existe', async () => {
    const { http, fixture, el } = await montar({ unidade: 'pompeia', curso: 'big-data' });
    escolherArquivo(el);
    digitar(el, 'input[type=password]', 'token-de-teste');
    el.querySelector('form')!.dispatchEvent(new Event('submit'));
    http
      .expectOne('/api/ppcs')
      .flush({ detail: 'esta versão já está cadastrada' }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();
    expect(el.querySelector('[role=alert]')?.textContent).toContain(
      'Esta versão já está cadastrada.',
    );
  });
});
