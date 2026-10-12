from fatecorg_crawler.extract import extrair_texto, normalizar_texto


def test_normaliza_hifenizacao_e_espacos():
    assert normalizar_texto("pedagó-\ngico   do  curso\n\n\n\nfim") == "pedagógico do curso\n\nfim"


def test_pdf_com_texto_nao_precisa_ocr(tmp_path, pdf_com_texto):
    caminho = tmp_path / "ppc.pdf"
    caminho.write_bytes(pdf_com_texto("Projeto Pedagógico do Curso. " * 40))
    texto = extrair_texto(caminho, min_chars=500)
    assert texto.paginas == 1
    assert "Projeto Pedagógico" in texto.texto
    assert not texto.precisa_ocr


def test_pdf_sem_texto_precisa_ocr(tmp_path, pdf_com_texto):
    caminho = tmp_path / "escaneado.pdf"
    caminho.write_bytes(pdf_com_texto(""))
    assert extrair_texto(caminho).precisa_ocr
