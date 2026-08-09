"""
Trata PDFs protegidos por senha.
"""

import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from logger import get_logger

log = get_logger("senha_pdf")


class PDFSenhaError(Exception):
    pass


def _somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _gerar_candidatos_senha(cpf: Optional[str], data_nascimento: Optional[str]) -> list:
    candidatos = []

    if cpf:
        cpf_digitos = _somente_digitos(cpf)
        if len(cpf_digitos) == 11:
            candidatos.append(cpf_digitos)
            candidatos.append(cpf_digitos[-6:])
            candidatos.append(cpf_digitos[-4:])
            candidatos.append(cpf_digitos[:4])
            candidatos.append(
                f"{cpf_digitos[0:3]}.{cpf_digitos[3:6]}.{cpf_digitos[6:9]}-{cpf_digitos[9:11]}"
            )

    if data_nascimento:
        dn_digitos = _somente_digitos(data_nascimento)
        if len(dn_digitos) == 8:
            candidatos.append(dn_digitos)
            candidatos.append(dn_digitos[4:8] + dn_digitos[2:4] + dn_digitos[0:2])

    vistos = set()
    unicos = []
    for c in candidatos:
        if c not in vistos:
            vistos.add(c)
            unicos.append(c)
    return unicos


def tentar_abrir_com_senha(
    caminho_pdf: Path,
    cpf_cliente: Optional[str] = None,
    data_nascimento_cliente: Optional[str] = None,
    senha_manual: Optional[str] = None,
):
    doc = fitz.open(caminho_pdf)

    if not doc.needs_pass:
        return doc

    candidatos = []
    if senha_manual:
        candidatos.append(senha_manual)
    candidatos.extend(_gerar_candidatos_senha(cpf_cliente, data_nascimento_cliente))

    for senha in candidatos:
        if doc.authenticate(senha):
            log.info("Senha encontrada para %s (estratégia automática)", caminho_pdf.name)
            return doc

    doc.close()
    raise PDFSenhaError(
        f"Nenhuma das {len(candidatos)} senhas testadas abriu o arquivo."
    )
