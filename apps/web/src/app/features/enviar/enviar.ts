import { httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { Api, mensagemDeErro } from '../../api/api';
import { TIPOS_DOCUMENTO, TipoDocumento, Unidade, Versao } from '../../api/tipos';
import { RotuloTipoPipe } from '../../shared/formatos';

const ACEITOS = '.pdf,.doc,.docx,.odt,.zip';

/**
 * Upload manual de um documento, por exemplo um PPC que o crawler não pode baixar do Drive.
 * O token do upload (API_TOKEN_UPLOAD) é digitado a cada envio e fica só na memória.
 */
@Component({
  selector: 'app-enviar',
  imports: [ReactiveFormsModule, RouterLink, RotuloTipoPipe],
  templateUrl: './enviar.html',
})
export class Enviar {
  private readonly api = inject(Api);
  private readonly rota = inject(ActivatedRoute);
  protected readonly tipos = TIPOS_DOCUMENTO;
  protected readonly aceitos = ACEITOS;

  protected readonly unidades = httpResource<Unidade[]>(() => this.api.url('/unidades'), {
    defaultValue: [],
  });

  protected readonly form = new FormGroup({
    unidade: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    curso: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    tipo_documento: new FormControl<TipoDocumento>('ppc', { nonNullable: true }),
    titulo: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(200)] }),
    token: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  protected readonly arquivo = signal<File | null>(null);
  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly enviado = signal<Versao | null>(null);
  protected readonly tentou = signal(false);

  private readonly unidadeEscolhida = toSignal(this.form.controls.unidade.valueChanges, {
    initialValue: this.form.controls.unidade.value,
  });
  protected readonly cursos = computed(
    () => this.unidades.value().find((u) => u.slug === this.unidadeEscolhida())?.cursos ?? [],
  );

  constructor() {
    // Vindo do banner de avisos: /enviar?unidade=pompeia&curso=...&tipo=ppc
    const q = this.rota.snapshot.queryParamMap;
    const tipo = q.get('tipo') as TipoDocumento | null;
    this.form.patchValue({
      unidade: q.get('unidade') ?? '',
      curso: q.get('curso') ?? '',
      ...(tipo && TIPOS_DOCUMENTO.includes(tipo) ? { tipo_documento: tipo } : {}),
    });
    this.form.controls.unidade.valueChanges.subscribe(() => this.form.controls.curso.setValue(''));
  }

  protected escolherArquivo(evento: Event): void {
    this.arquivo.set((evento.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected enviar(): void {
    this.tentou.set(true);
    this.erro.set(null);
    const arquivo = this.arquivo();
    if (this.form.invalid || !arquivo || this.enviando()) {
      this.form.markAllAsTouched();
      return;
    }
    const { token, ...campos } = this.form.getRawValue();
    this.enviando.set(true);
    this.api.enviar({ ...campos, arquivo }, token).subscribe({
      next: (versao) => {
        this.enviando.set(false);
        this.enviado.set(versao);
        this.form.controls.token.reset();
      },
      error: (e: unknown) => {
        this.enviando.set(false);
        this.erro.set(mensagemDeErro(e));
      },
    });
  }

  protected novoEnvio(): void {
    this.enviado.set(null);
    this.arquivo.set(null);
    this.tentou.set(false);
    this.form.controls.titulo.reset();
  }
}
