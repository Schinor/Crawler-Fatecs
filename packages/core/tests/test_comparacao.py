from fatecorg_core.comparacao import TrechoDiff, comparar, linhas_logicas

ANTES = """Perfil do egresso
O tecnólogo em
Sistemas Inteligentes atua
no desenvolvimento.

Carga horária total: 2400 horas.

Estágio de 240 horas."""

DEPOIS = """Perfil do egresso
O tecnólogo em Sistemas Inteligentes atua no desenvolvimento.

Carga horária total: 2800 horas.

Estágio de 240 horas.

Extensão curricular de 280 horas."""


def test_linhas_logicas_desfazem_as_quebras_do_pdf_justificado():
    assert linhas_logicas(ANTES)[:2] == [
        "Perfil do egresso",
        "O tecnólogo em Sistemas Inteligentes atua no desenvolvimento.",
    ]
    assert linhas_logicas("Bibliografia Básica:\n\uf0b7 LAKATOS, E. M. Metodologia") == [
        "Bibliografia Básica:",
        "LAKATOS, E. M. Metodologia",  # marcador de lista da fonte de símbolos removido
    ]


def test_quebra_de_linha_diferente_nao_conta_como_mudanca():
    r = comparar(ANTES, DEPOIS)
    assert r.blocos[0].tipo == "igual"
    assert r.blocos[0].trechos[0].texto.startswith("Perfil do egresso")


def test_mudanca_marcada_por_palavra_e_paragrafo_novo():
    r = comparar(ANTES, DEPOIS)
    alterados = [b for b in r.blocos if b.tipo == "alterado"]
    assert alterados[0].trechos == [
        TrechoDiff("igual", "Carga horária total:"),
        TrechoDiff("removido", "2400"),
        TrechoDiff("adicionado", "2800"),
        TrechoDiff("igual", "horas."),
    ]
    assert alterados[1].trechos == [TrechoDiff("adicionado", "Extensão curricular de 280 horas.")]
    assert r.palavras_removidas == 1
    assert r.palavras_adicionadas == 6  # "2800" e o parágrafo novo
    assert 0.7 < r.semelhanca < 1


def test_textos_iguais():
    r = comparar(ANTES, ANTES)
    assert [b.tipo for b in r.blocos] == ["igual"]
    assert (r.palavras_adicionadas, r.palavras_removidas, r.semelhanca) == (0, 0, 1.0)
    assert comparar("", "").semelhanca == 1.0


def test_trecho_reescrito_aparece_inteiro_e_nao_palavra_a_palavra():
    antes = "Ementa: Introdução à administração e às funções gerenciais."
    depois = "Ementa: Estudo de casos de marketing digital em pequenas empresas."
    (bloco,) = comparar(antes, depois).blocos
    assert bloco.trechos == [TrechoDiff("removido", antes), TrechoDiff("adicionado", depois)]
