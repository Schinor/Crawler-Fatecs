import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';

describe('App', () => {
  it('mostra a navegação principal e o link para pular ao conteúdo', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const links = [...el.querySelectorAll('nav a')].map((a) => a.textContent?.trim());
    expect(links).toEqual(['Unidades', 'Documentos', 'Enviar']);
    expect(el.querySelector('a.pular')?.getAttribute('href')).toBe('#conteudo');
  });
});
