"""
Configuração central de logs. Grava em arquivo e também mostra no terminal.
"""

import logging
from config import ARQUIVO_LOG, PASTA_LOGS

PASTA_LOGS.mkdir(parents=True, exist_ok=True)


def get_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")
    file_handler.setFormatter(formato)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)
    logger.addHandler(console_handler)

    return logger
