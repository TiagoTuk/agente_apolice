"""
Fase 2a - Leitura de PDFs digitais (texto selecionável).
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional

from logger import get_logger
from senha_pdf import tentar_abrir_com_senha, PDFSenhaError

log = get_logger("leitor_pdf")

MIN_CARACTERES_TEXTO_VALIDO = 30


def extrair_texto(caminho_pdf: Path, cpf_cliente: Optional[str] = None,
                   data_nascimento_cliente: Optional[str] = None) -> str:
    try:
        doc = fitz.open(caminho_pdf)
    except Exception as e:
        log.error("Falha ao abrir %s: %s", caminho_pdf.name, e)
        return ""

    if doc.needs_pass:
        try:
            doc = tentar_abrir_com_senha(
                caminho_pdf, cpf_cliente, data_nascimento_cliente
            )
        except PDFSenhaError as e:
            log.warning("PDF protegido, senha não encontrada: %s (%s)", caminho_pdf.name, e)
            raise

    texto_completo = []
    for pagina in doc:
        texto_completo.append(pagina.get_text())
    doc.close()

    texto = "\n".join(texto_completo).strip()

    if len(texto) < MIN_CARACTERES_TEXTO_VALIDO:
        log.info("Pouco/nenhum texto extraível em %s (provável PDF escaneado)", caminho_pdf.name)
        return ""

    return texto
