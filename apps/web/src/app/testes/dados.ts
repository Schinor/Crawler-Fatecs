// Dados de teste parecidos com os reais (Pompeia e Marília).
import { Aviso, Unidade, Versao } from '../api/tipos';

export const UNIDADES: Unidade[] = [
  {
    slug: 'pompeia',
    nome: 'Fatec Pompeia',
    cidade: 'Pompeia',
    site_url: 'https://www.fatecpompeia.edu.br',
    plataforma: 'google_sites',
    ativa: true,
    cursos: [
      {
        slug: 'sistemas-inteligentes',
        nome: 'CST em Sistemas Inteligentes',
        url: 'https://www.fatecpompeia.edu.br/si',
      },
      {
        slug: 'big-data',
        nome: 'CST em Big Data no Agronegócio',
        url: 'https://www.fatecpompeia.edu.br/bigdata',
      },
    ],
  },
  {
    slug: 'marilia',
    nome: 'Fatec Marília',
    cidade: 'Marília',
    site_url: 'https://fatecmarilia.cps.sp.gov.br',
    plataforma: 'wordpress',
    ativa: true,
    cursos: [
      {
        slug: 'alimentos',
        nome: 'CST em Alimentos',
        url: 'https://fatecmarilia.cps.sp.gov.br/alimentos',
      },
    ],
  },
];

export function versao(parcial: Partial<Versao> = {}): Versao {
  const sha256 = parcial.sha256 ?? 'a'.repeat(64);
  const unidade = parcial.unidade ?? 'marilia';
  const curso = parcial.curso ?? 'alimentos';
  const base = `/ppcs/${unidade}/${curso}/${sha256}`;
  return {
    unidade,
    curso,
    curso_nome: 'CST em Alimentos',
    tipo_documento: 'matriz',
    origem: 'crawler',
    formato: 'pdf',
    sha256,
    tamanho_bytes: 250_000,
    paginas: 2,
    precisa_ocr: false,
    titulo: 'Matriz curricular 2024',
    pagina_url: 'https://fatecmarilia.cps.sp.gov.br/alimentos',
    arquivo_url: 'https://bkpsitecpsnew.blob.core.windows.net/matriz.pdf',
    coletado_em: '2026-10-12T03:00:00Z',
    links: { arquivo: `${base}/arquivo`, texto: `${base}/texto` },
    ...parcial,
  };
}

export function aviso(parcial: Partial<Aviso> = {}): Aviso {
  return {
    tipo: 'drive_bloqueado',
    unidade_slug: 'pompeia',
    curso_slug: 'sistemas-inteligentes',
    curso_nome: 'CST em Sistemas Inteligentes',
    tipo_documento: 'ppc',
    pagina_url: 'https://www.fatecpompeia.edu.br/si',
    arquivo_url: 'https://drive.google.com/file/d/abc/preview',
    titulo_link: 'PPC CST Sistemas Inteligentes.pdf',
    mensagem:
      'O documento está no Google Drive e o robots.txt do Drive proíbe o download automático.',
    detectado_em: '2026-10-12T03:00:00Z',
    visto_em: '2026-11-07T20:39:00Z',
    ...parcial,
  };
}
