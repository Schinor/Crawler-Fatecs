import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { aviso } from '../testes/dados';
import { AvisosBanner } from './avisos-banner';

describe('AvisosBanner', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideRouter([])] }));

  it('não aparece sem avisos', async () => {
    const fixture = TestBed.createComponent(AvisosBanner);
    fixture.componentRef.setInput('avisos', []);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('section')).toBeNull();
  });

  it('liga cada aviso ao formulário de envio já preenchido', async () => {
    const fixture = TestBed.createComponent(AvisosBanner);
    fixture.componentRef.setInput('avisos', [aviso()]);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h2')?.textContent).toContain('1 documento precisa');
    const enviar = [...el.querySelectorAll('a')].find((a) => a.textContent === 'enviar o arquivo');
    expect(enviar?.getAttribute('href')).toBe(
      '/enviar?unidade=pompeia&curso=sistemas-inteligentes&tipo=ppc',
    );
  });

  it('mostra título e mensagem como texto, nunca como HTML (seguranca.md, A-8)', async () => {
    const fixture = TestBed.createComponent(AvisosBanner);
    const malicioso = '<img src=x onerror="alert(1)">';
    fixture.componentRef.setInput('avisos', [
      aviso({ titulo_link: malicioso, mensagem: malicioso }),
    ]);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('img')).toBeNull();
    expect(el.textContent).toContain(malicioso);
  });
});
