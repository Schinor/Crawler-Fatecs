# Decisões e pendências com a parceira

Registro das respostas às pendências do plano. Cada decisão tem data, para sabermos o que mudou
desde então.

## Decididas

| Data | Tema | Decisão | Impacto |
| --- | --- | --- | --- |
| 12/10/2026 | Nome do sistema | **FatecOrg** | Pacotes `fatecorg-*`, CLI `fatecorg-crawler` |
| 12/10/2026 | Unidades iniciais | **Fatec Pompeia** e **Fatec Marília**. As demais Fatecs do Polo 08 entram depois | `apps/crawler/seeds/unidades.yaml`; inventário em `inventario-sites.md` |
| 12/10/2026 | Frequência de coleta | **1 vez por semana**, de madrugada (sugestão: domingo às 03h, `0 3 * * 0`) | Tarefa C9 (agendamento) |
| 12/10/2026 | Campos do PPC | Por enquanto o PPC é guardado **inteiro** (arquivo + texto extraído), sem extrair campos | Os campos específicos ainda serão definidos (ver abaixo) |
| 12/10/2026 | Object storage | **Garage** (S3 compatível, auto-hospedável) no lugar do MinIO | `infra/docker-compose.yml`, `make infra-up` |
| 12/10/2026 | Responsável pelo crawler | **Marcio** é o contato no User-Agent do crawler | E-mail só no `.env` local |
| 12/10/2026 | Notificações | Por enquanto só o responsável pelo projeto (Marcio) recebe | O e-mail fica em `NOTIFICACAO_DESTINATARIOS` no `.env` local, nunca no repositório |

## Em aberto

- [ ] **Definir os campos específicos do PPC** que importam para os relatórios: por exemplo, carga
  horária, eixo tecnológico, disciplinas, perfil do egresso e data de aprovação. Até lá, a coluna
  `campos` (JSONB) da tabela `ppc_versao` fica vazia e a extração estruturada (Fase 4) não começa.
  Responsável: grupo + parceira.
- [ ] **Lista oficial das Fatecs do Polo 08** para completar o seed (hoje: Pompeia e Marília).
- [ ] **Marília não publica o PPC completo**, só matrizes curriculares e ementários. Decidir se
  esses documentos entram como "documentos curriculares" do curso ou se pedimos o PPC à unidade.
  Ver `inventario-sites.md`.
- [ ] **Pompeia, curso MAP**: a página do curso não tem o PPC; só o ementário aparece em
  `/secretaria/ementa`.
