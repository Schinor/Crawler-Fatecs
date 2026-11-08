import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { mensagemDeErro } from '../../api/api';
import { Auth } from '../../core/auth';

@Component({
  selector: 'app-entrar',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './entrar.html',
})
export class Entrar {
  private readonly router = inject(Router);
  private readonly rota = inject(ActivatedRoute);
  protected readonly auth = inject(Auth);

  protected readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    senha: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });
  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly tentou = signal(false);
  /** Logado e ainda em /entrar?voltar=...: a guarda recusou a página pedida. */
  protected readonly veioDeOutraPagina = this.rota.snapshot.queryParamMap.has('voltar');

  /** Só caminhos internos: `//site` seria lido como outro domínio. */
  private destino(): string {
    const voltar = this.rota.snapshot.queryParamMap.get('voltar') ?? '/';
    return voltar.startsWith('/') && !voltar.startsWith('//') ? voltar : '/';
  }

  protected entrar(): void {
    this.tentou.set(true);
    this.erro.set(null);
    if (this.form.invalid || this.enviando()) {
      return;
    }
    const { email, senha } = this.form.getRawValue();
    this.enviando.set(true);
    this.auth.entrar(email, senha).subscribe({
      next: () => {
        this.enviando.set(false);
        void this.router.navigateByUrl(this.destino());
      },
      error: (e: unknown) => {
        this.enviando.set(false);
        this.form.controls.senha.reset();
        this.erro.set(mensagemDeErro(e));
      },
    });
  }
}
