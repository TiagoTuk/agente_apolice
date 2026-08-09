"""
Fase 2b - OCR para PDFs escaneados (sem texto selecionável).
Requer Tesseract instalado no sistema.
"""

from pathlib import Path
import io

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from logger import get_logger

log = get_logger("ocr")

DPI_RENDERIZACAO = 300
IDIOMA_OCR = "por"


def extrair_texto_via_ocr(caminho_pdf: Path) -> str:
    try:
        doc = fitz.open(caminho_pdf)
    except Exception as e:
        log.error("Falha ao abrir %s para OCR: %s", caminho_pdf.name, e)
        return ""

    zoom = DPI_RENDERIZACAO / 72
    matriz = fitz.Matrix(zoom, zoom)

    textos_paginas = []
    for i, pagina in enumerate(doc):
        try:
            pix = pagina.get_pixmap(matrix=matriz)
            imagem = Image.open(io.BytesIO(pix.tobytes("png")))
            texto = pytesseract.image_to_string(imagem, lang=IDIOMA_OCR)
            textos_paginas.append(texto)
        except Exception as e:
            log.warning("Erro no OCR da página %d de %s: %s", i + 1, caminho_pdf.name, e)

    doc.close()
    texto_final = "\n".join(textos_paginas).strip()
    log.info("OCR concluído para %s (%d caracteres extraídos)", caminho_pdf.name, len(texto_final))
    return texto_final
