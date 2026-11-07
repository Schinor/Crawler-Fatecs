import { Pipe, PipeTransform } from '@angular/core';

import { OrigemVersao, TipoDocumento, Versao } from '../api/tipos';

const ROTULOS_TIPO: Record<TipoDocumento, string> = {
  ppc: 'PPC',
  matriz: 'Matriz curricular',
  ementario: 'Ementário',
};

const ROTULOS_ORIGEM: Record<OrigemVersao, string> = {
  crawler: 'Coletado do site',
  upload: 'Enviado manualmente',
};

export function rotuloTipo(tipo: TipoDocumento): string {
  return ROTULOS_TIPO[tipo] ?? tipo;
}

export function rotuloOrigem(origem: OrigemVersao): string {
  return ROTULOS_ORIGEM[origem] ?? origem;
}

export function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
}

/** Um documento publicado (mesmo link de origem) e as versões que ele já teve. */
export interface Documento {
  chave: string;
  versoes: Versao[]; // da mais recente para a mais antiga
}

export interface Grupo {
  tipo: TipoDocumento;
  documentos: Documento[];
}

/**
 * Uma unidade pode publicar vários documentos do mesmo tipo ao mesmo tempo (Marília tem uma
 * matriz por grade curricular). Versões de um mesmo documento são as que vieram do mesmo link
 * com conteúdo diferente. Uploads não têm link: cada um conta como documento próprio.
 */
function chaveDocumento(v: Versao): string {
  return v.arquivo_url ?? `upload:${v.sha256}`;
}

/** Agrupa por tipo (PPC, matriz, ementário) e, dentro dele, por documento. */
export function agruparPorTipo(versoes: readonly Versao[]): Grupo[] {
  const ordem: TipoDocumento[] = ['ppc', 'matriz', 'ementario'];
  const recentes = [...versoes].sort((a, b) => b.coletado_em.localeCompare(a.coletado_em));
  return ordem
    .map((tipo) => {
      const documentos = new Map<string, Versao[]>();
      for (const v of recentes.filter((x) => x.tipo_documento === tipo)) {
        const chave = chaveDocumento(v);
        documentos.set(chave, [...(documentos.get(chave) ?? []), v]);
      }
      return {
        tipo,
        documentos: [...documentos].map(([chave, lista]) => ({ chave, versoes: lista })),
      };
    })
    .filter((g) => g.documentos.length > 0);
}

@Pipe({ name: 'rotuloTipo' })
export class RotuloTipoPipe implements PipeTransform {
  transform(tipo: TipoDocumento): string {
    return rotuloTipo(tipo);
  }
}

@Pipe({ name: 'rotuloOrigem' })
export class RotuloOrigemPipe implements PipeTransform {
  transform(origem: OrigemVersao): string {
    return rotuloOrigem(origem);
  }
}

@Pipe({ name: 'tamanho' })
export class TamanhoPipe implements PipeTransform {
  transform(bytes: number): string {
    return tamanho(bytes);
  }
}
