"""
Fase 1 - Scanner de arquivos.

Não depende de uma estrutura fixa de pastas. Para cada cliente, procura
recursivamente por QUALQUER subpasta cujo nome seja um ano (4 dígitos,
ex: "2019", "2025") e usa a mais recente encontrada — não fica restrito
a uma lista fixa, então funciona tanto para clientes que não renovam há
anos quanto para os mais recentes.

Se o cliente não tiver NENHUMA subpasta de ano (caso comum de cliente
novo, cuja primeira apólice ainda não passou por renovação), o agente
cai para um modo alternativo: procura o arquivo de apólice direto na
pasta raiz do cliente, recursivamente, ignorando a exigência de pasta
de ano.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import unicodedata

from config import PASTA_ENTRADA, PALAVRAS_CHAVE_DOCUMENTO
from logger import get_logger

log = get_logger("scanner")

PADRAO_NOME_DE_ANO = re.compile(r"^(19|20)\d{2}$")


@dataclass
class ClienteEncontrado:
    cliente: str
    ano_encontrado: Optional[str] = None
    arquivos_apolice: list = field(default_factory=list)
    caminho_pasta_ano: Optional[Path] = None
    erro: Optional[str] = None


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def _eh_pasta_de_ano(pasta: Path) -> bool:
    return pasta.is_dir() and bool(PADRAO_NOME_DE_ANO.match(pasta.name.strip()))


def _encontrar_todas_pastas_ano(pasta_cliente: Path) -> dict:
    por_ano: dict = {}
    for caminho in pasta_cliente.rglob("*"):
        if _eh_pasta_de_ano(caminho):
            ano = caminho.name.strip()
            por_ano.setdefault(ano, []).append(caminho)
    return por_ano


def _listar_subpastas_para_diagnostico(pasta_cliente: Path, profundidade_max: int = 3) -> list:
    nomes = []
    try:
        for caminho in pasta_cliente.rglob("*"):
            if caminho.is_dir():
                profundidade = len(caminho.relative_to(pasta_cliente).parts)
                if profundidade <= profundidade_max:
                    nomes.append(str(caminho.relative_to(pasta_cliente)))
    except Exception:
        pass
    return nomes


def _encontrar_arquivos_apolice(pasta: Path) -> list:
    candidatos = []
    for arquivo in pasta.glob("*.pdf"):
        nome_normalizado = _normalizar(arquivo.name)
        if any(_normalizar(kw) in nome_normalizado for kw in PALAVRAS_CHAVE_DOCUMENTO):
            candidatos.append(arquivo)

    if not candidatos:
        return []

    if len(candidatos) == 1:
        return candidatos

    candidatos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    log.warning(
        "Múltiplas apólices encontradas em %s — usando a mais recente: %s",
        pasta, candidatos[0].name,
    )
    return [candidatos[0]]


def escanear_clientes(pasta_entrada: Path = PASTA_ENTRADA) -> list:
    resultados = []

    if not pasta_entrada.exists():
        log.error("Pasta de entrada não existe: %s", pasta_entrada)
        return resultados

    pastas_clientes = sorted(p for p in pasta_entrada.iterdir() if p.is_dir())
    log.info("Encontrados %d clientes em %s", len(pastas_clientes), pasta_entrada)

    for pasta_cliente in pastas_clientes:
        resultado = ClienteEncontrado(cliente=pasta_cliente.name)

        pastas_por_ano = _encontrar_todas_pastas_ano(pasta_cliente)

        if pastas_por_ano:
            ano_usado = max(pastas_por_ano.keys())
            pastas_ano_encontradas = pastas_por_ano[ano_usado]
            resultado.ano_encontrado = ano_usado

            todos_arquivos = []
            for pasta_ano in pastas_ano_encontradas:
                arquivos = _encontrar_arquivos_apolice(pasta_ano)
                if arquivos:
                    todos_arquivos.extend(arquivos)
                resultado.caminho_pasta_ano = pasta_ano

            if not todos_arquivos:
                resultado.erro = "Pasta do ano encontrada, mas nenhum arquivo de apólice dentro"
                log.warning("[%s] %s (ano=%s)", resultado.cliente, resultado.erro, ano_usado)
            else:
                resultado.arquivos_apolice = todos_arquivos
                log.info(
                    "[%s] ano=%s | %d apólice(s) encontrada(s)",
                    resultado.cliente, ano_usado, len(todos_arquivos),
                )

        else:
            arquivos = _encontrar_arquivos_apolice(pasta_cliente)
            if not arquivos:
                for subpasta in pasta_cliente.rglob("*"):
                    if subpasta.is_dir():
                        arquivos.extend(_encontrar_arquivos_apolice(subpasta))

            if arquivos:
                resultado.ano_encontrado = "sem pasta de ano (cliente novo)"
                resultado.arquivos_apolice = arquivos
                log.info(
                    "[%s] Sem pasta de ano — tratado como cliente novo | %d apólice(s) encontrada(s)",
                    resultado.cliente, len(arquivos),
                )
            else:
                resultado.erro = "Nenhuma pasta de ano e nenhuma apólice encontrada na pasta do cliente"
                subpastas_existentes = _listar_subpastas_para_diagnostico(pasta_cliente)
                log.warning(
                    "[%s] %s | subpastas existentes (até 3 níveis): %s",
                    resultado.cliente, resultado.erro, subpastas_existentes,
                )

        resultados.append(resultado)

    return resultados


if __name__ == "__main__":
    resultados = escanear_clientes()
    print(f"\n{'='*60}")
    print(f"Total de clientes processados: {len(resultados)}")
    print(f"{'='*60}\n")
    for r in resultados:
        status = "OK" if r.arquivos_apolice else "ERRO"
        nomes_arquivos = [a.name for a in r.arquivos_apolice]
        print(f"[{status}] {r.cliente} | ano={r.ano_encontrado} | "
              f"arquivos={nomes_arquivos} | erro={r.erro}")
