"""
Configurações centrais do Agente de Documentos da Corretora.
"""

from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
PASTA_ENTRADA = BASE_DIR / "entrada"
PASTA_RESULTADO = BASE_DIR / "resultado"
PASTA_LOGS = BASE_DIR / "logs"

ARQUIVO_EXCEL_SAIDA = PASTA_RESULTADO / "apolices.xlsx"
ARQUIVO_LOG = PASTA_LOGS / "execucao.log"

# NOTA: não é mais usado pelo scanner.py — ele agora detecta automaticamente
# QUALQUER pasta de ano (4 dígitos) e usa a mais recente disponível para
# cada cliente. Mantido aqui só de referência.
ANO_ATUAL = datetime.now().year
ANOS_PARA_BUSCAR = [str(ANO_ATUAL), str(ANO_ATUAL - 1)]

# Antes buscava arquivos com "apolice"/"apólice" no nome. Trocado para
# "proposta" porque, em algumas seguradoras (ex: HDI), a data de
# nascimento aparece na proposta mas não na apólice em si.
PALAVRAS_CHAVE_DOCUMENTO = ["proposta"]

# Seguradoras cujos documentos têm os dados do segurado mais para o
# final (ex: só na página 3-4) — para essas, mandamos mais texto para
# a IA do que o padrão. Chave: palavra que identifica a seguradora no
# texto do documento (comparação sem acento, case-insensitive).
LIMITE_CARACTERES_PROMPT_PADRAO = 2500
LIMITES_CARACTERES_POR_SEGURADORA = {
    "hdi": 10000,
}

CAMPOS_EXTRACAO = {
    "nome": "Nome completo do segurado ou titular da apólice",
    "data_nascimento": "Data de nascimento do segurado, no formato DD/MM/AAAA",
}

CAMPOS_OBRIGATORIOS = ["nome", "data_nascimento"]

# Ollama (IA local)
OLLAMA_URL = "http://localhost:11434/api/generate"
# Modelo leve (3B parâmetros) — roda bem em máquinas com 8-16GB de RAM.
# Se sua máquina tiver bastante RAM sobrando (16GB+), pode trocar para
# "llama3.1" (8B) para mais precisão, mas em máquinas com RAM mais justa
# isso tende a causar timeout ou erro 500 do Ollama por falta de memória.
OLLAMA_MODELO = "llama3.2"
# Aumentado de 120s para 300s: modelos podem levar mais de 2 minutos
# para carregar na memória na primeira chamada (cold start).
OLLAMA_TIMEOUT = 300

USAR_REGEX_PRIMEIRO = True

MAX_WORKERS = 4
