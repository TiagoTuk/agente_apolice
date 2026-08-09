"""
Extração de campos via LLM local (Ollama).
Requer o Ollama rodando localmente (ollama serve) com um modelo baixado
(ollama pull llama3.2). Nada aqui sai da sua máquina.
"""

import json
import re
import unicodedata

import requests

from config import (
    CAMPOS_EXTRACAO,
    OLLAMA_URL,
    OLLAMA_MODELO,
    OLLAMA_TIMEOUT,
    LIMITE_CARACTERES_PROMPT_PADRAO,
    LIMITES_CARACTERES_POR_SEGURADORA,
)
from logger import get_logger

log = get_logger("extrator_ia")

# Mantém o modelo carregado na memória por mais tempo entre chamadas,
# evitando ter que recarregar (cold start) se o processamento de um
# documento para o outro demorar um pouco (ex: OCR de um PDF grande).
OLLAMA_KEEP_ALIVE = "30m"


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def _detectar_limite_caracteres(texto_documento: str) -> int:
    """Verifica se o documento é de alguma seguradora com limite
    especial configurado (ex: HDI, cujos dados do segurado só aparecem
    na página 3-4). Só precisa olhar o início do texto pra identificar
    a seguradora, mesmo que o limite final seja bem maior."""
    trecho_inicial = _normalizar(texto_documento[:3000])
    for chave, limite in LIMITES_CARACTERES_POR_SEGURADORA.items():
        if _normalizar(chave) in trecho_inicial:
            log.info("Seguradora '%s' detectada — usando limite de %d caracteres para a IA", chave, limite)
            return limite
    return LIMITE_CARACTERES_PROMPT_PADRAO


def _montar_prompt(texto_documento: str, campos: dict, limite_caracteres: int) -> str:
    lista_campos = "\n".join(
        f'  - "{campo}": {descricao}' for campo, descricao in campos.items()
    )
    exemplo_json = json.dumps(
        {campo: "" for campo in campos}, ensure_ascii=False, indent=2
    )

    return f"""Você é um assistente que extrai informações de documentos de apólices de seguro.

Extraia SOMENTE os seguintes campos do texto abaixo:
{lista_campos}

Regras importantes:
- Responda APENAS com um objeto JSON válido, sem nenhum texto antes ou depois.
- Se não encontrar um campo, deixe o valor como string vazia "".
- Não invente informações que não estejam no texto.
- Datas devem estar no formato DD/MM/AAAA.

Formato esperado da resposta:
{exemplo_json}

Texto do documento:
\"\"\"
{texto_documento[:limite_caracteres]}
\"\"\"

Responda apenas com o JSON:"""


def _extrair_json_da_resposta(resposta_texto: str) -> dict:
    texto = resposta_texto.strip()

    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log.error("Não foi possível parsear JSON da resposta do modelo: %s", texto[:200])
    return {}


def extrair_via_ollama(texto_documento: str, campos: dict = None) -> dict:
    """Pede ao modelo local só os campos passados em `campos` (dict
    {nome_campo: descricao}). Se None, usa todos os campos configurados
    em CAMPOS_EXTRACAO. Passar só os campos que realmente faltam (ex:
    quando o nome já foi confirmado via nome da pasta) deixa o prompt
    menor e a resposta mais rápida."""
    campos = campos or CAMPOS_EXTRACAO
    limite_caracteres = _detectar_limite_caracteres(texto_documento)
    prompt = _montar_prompt(texto_documento, campos, limite_caracteres)

    payload = {
        "model": OLLAMA_MODELO,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": 0,
        },
    }

    try:
        resposta = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        resposta.raise_for_status()
    except requests.exceptions.ConnectionError:
        log.error(
            "Não foi possível conectar ao Ollama em %s. "
            "Verifique se o servidor está rodando (`ollama serve`).",
            OLLAMA_URL,
        )
        resultado = {campo: "" for campo in campos}
        resultado["erro"] = "ollama_offline"
        return resultado
    except requests.exceptions.Timeout:
        log.error("Timeout ao aguardar resposta do Ollama (%ds)", OLLAMA_TIMEOUT)
        resultado = {campo: "" for campo in campos}
        resultado["erro"] = "timeout"
        return resultado
    except requests.exceptions.HTTPError as e:
        log.error("Erro HTTP do Ollama: %s", e)
        resultado = {campo: "" for campo in campos}
        resultado["erro"] = "http_error"
        return resultado

    corpo = resposta.json()
    texto_resposta = corpo.get("response", "")

    dados = _extrair_json_da_resposta(texto_resposta)

    resultado = {campo: dados.get(campo, "") for campo in campos}
    return resultado
