// Apelidos dos tipos gerados do OpenAPI (esquema.ts). Não edite esquema.ts à mão:
// rode `npm run api:tipos` depois de `uv run python scripts/exportar-openapi.py`.
import type { components } from './esquema';

type Esquemas = components['schemas'];

export type Unidade = Esquemas['Unidade'];
export type CursoSeed = Esquemas['CursoSeed'];
export type Versao = Esquemas['Versao'];
export type Aviso = Esquemas['Aviso'];
export type TipoDocumento = Esquemas['TipoDocumento'];
export type OrigemVersao = Esquemas['OrigemVersao'];

export const TIPOS_DOCUMENTO: readonly TipoDocumento[] = ['ppc', 'matriz', 'ementario'];
