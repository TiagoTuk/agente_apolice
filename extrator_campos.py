"""
Fase 3 - Extração dos campos a partir do texto.

Estratégia, em ordem de prioridade:
1. Busca pelo NOME DA PASTA do cliente diretamente no texto do documento.
   Como a pasta é sempre nomeada com o nome do cliente (pessoa física ou
   jurídica), essa é a fonte mais confiável que temos — não depende de
   adivinhar qual rótulo ("Segurado", "Titular", "Nome Completo"...) a
   seguradora usou. Some o nome da pasta bate com um trecho do texto,
   usamos ele com confiança alta.
2. Se a busca por pasta não achar nada, cai para os rótulos comuns via
   regex (mais frágil, mas ainda rápido e sem custo de IA).
3. Se nada disso encontrar todos os campos obrigatórios, cai para o LLM
   local via Ollama (extrator_ia.py) — o mais lento e "caro".

A data de nascimento continua sendo buscada só por rótulo (regex), já
que não temos uma "fonte confiável" equivalente ao nome da pasta para
ela.
"""

import re
import unicodedata

from config import CAMPOS_OBRIGATORIOS, USAR_REGEX_PRIMEIRO
from logger import get_logger
from extrator_ia import extrair_via_ollama

log = get_logger("extrator_campos")

# ---------------------------------------------------------------------------
# Estratégia 1: nome da pasta do cliente
# ---------------------------------------------------------------------------

# Tamanho mínimo para considerar o nome da pasta válido para busca —
# evita falsos positivos com nomes de pasta muito curtos/genéricos.
TAMANHO_MINIMO_NOME_PASTA = 5


def _normalizar_para_comparacao(texto: str) -> str:
    """Remove acentos e uniformiza espaços/caixa, para comparar nomes
    de forma tolerante a pequenas diferenças de grafia entre a pasta
    e o texto do PDF."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def _limpar_nome_pasta(nome_pasta: str) -> str:
    """Remove anotações extras que costumam aparecer no nome da pasta,
    tipo '-SOGRO IR.GELSON' ou observações depois de um hífen, mantendo
    só o nome do cliente/empresa em si."""
    nome = re.split(r"\s*-\s*", nome_pasta)[0]
    return nome.strip()


def _buscar_nome_por_pasta(texto: str, nome_cliente_pasta: str):
    """Tenta confirmar o nome do cliente (a partir do nome da pasta)
    dentro do texto do documento. Retorna o nome (como está na pasta,
    já limpo) se encontrar, ou None caso contrário."""
    if not nome_cliente_pasta:
        return None

    nome_base = _limpar_nome_pasta(nome_cliente_pasta)
    if len(nome_base) < TAMANHO_MINIMO_NOME_PASTA:
        return None

    nome_normalizado = _normalizar_para_comparacao(nome_base)
    texto_normalizado = _normalizar_para_comparacao(texto)

    # Tentativa 1: o nome completo da pasta aparece literalmente no texto.
    if nome_normalizado in texto_normalizado:
        return nome_base

    # Tentativa 2: para nomes com 2+ palavras (típico de PF), aceita se
    # o primeiro E o último token aparecerem ambos no texto, mesmo que
    # não estejam juntos ou na mesma ordem — tolera nomes do meio
    # abreviados ou omitidos, formatação diferente, etc.
    tokens = [t for t in nome_normalizado.split() if len(t) > 2]
    if len(tokens) >= 2:
        primeiro, ultimo = tokens[0], tokens[-1]
        achou_primeiro = re.search(r"\b" + re.escape(primeiro) + r"\b", texto_normalizado)
        achou_ultimo = re.search(r"\b" + re.escape(ultimo) + r"\b", texto_normalizado)
        if achou_primeiro and achou_ultimo:
            return nome_base

    return None


# ---------------------------------------------------------------------------
# Estratégia 2: rótulos comuns (Segurado, Titular, Nome Completo...)
# ---------------------------------------------------------------------------

# Propositalmente NÃO incluímos a palavra solta "Nome" — ela aparece
# várias vezes no documento (nome do produto, nome da seguradora, etc.)
# e gerava falsos positivos. O rótulo precisa estar no início de uma
# linha (não no meio de uma frase qualquer).
PADROES_NOME = [
    r"^[ \t]*(?:Segurado|Nome\s+Completo|Nome\s+do\s+Segurado|Titular)\s*:?[ \t]*\n?[ \t]*([A-ZÀ-Ú][A-Za-zÀ-ú \t]{4,60})",
]

PADROES_DATA_NASCIMENTO = [
    r"^[ \t]*(?:Nascimento|Data\s+de\s+Nascimento|Dt\.?\s*Nasc\.?)\s*:?[ \t]*\n?[ \t]*(\d{2}[/-]\d{2}[/-]\d{4})",
]

PALAVRAS_PROIBIDAS_NOME = {
    "reparo", "troca", "vidro", "vidros", "cobertura", "sinistro",
    "sinistros", "seguradora", "produto", "endereco", "endereço",
    "pagamento", "clausula", "cláusula", "mundo", "brasil", "efetuara",
    "efetuará", "apolice", "apólice", "contrato", "vigencia", "vigência",
    "franquia", "premio", "prêmio",
}


def _limpar_nome_capturado(bruto: str) -> str:
    nome = bruto.strip().split("\n")[0].strip()
    return re.sub(r"\s+", " ", nome)


def _nome_parece_valido(candidato: str) -> bool:
    if not candidato or len(candidato) < 5 or len(candidato) > 60:
        return False
    if any(c.isdigit() for c in candidato):
        return False
    palavras = candidato.lower().split()
    if len(palavras) < 2:
        return False
    if any(p in PALAVRAS_PROIBIDAS_NOME for p in palavras):
        return False
    return True


def _buscar_por_rotulo(texto: str) -> dict:
    resultado = {}

    for padrao in PADROES_NOME:
        m = re.search(padrao, texto, re.MULTILINE)
        if m:
            candidato = _limpar_nome_capturado(m.group(1))
            if _nome_parece_valido(candidato):
                resultado["nome"] = candidato
                break
            else:
                log.info("Candidato a nome rejeitado pelo filtro de sanidade: %r", candidato)

    for padrao in PADROES_DATA_NASCIMENTO:
        m = re.search(padrao, texto, re.MULTILINE)
        if m:
            resultado["data_nascimento"] = m.group(1).replace("-", "/")
            break

    return resultado


# ---------------------------------------------------------------------------
# Orquestração das 3 estratégias
# ---------------------------------------------------------------------------

def _campos_completos(dados: dict) -> bool:
    return all(dados.get(campo) for campo in CAMPOS_OBRIGATORIOS)


def extrair_campos(texto: str, nome_arquivo: str = "", nome_cliente_pasta: str = "") -> dict:
    if not texto or not texto.strip():
        log.warning("Texto vazio recebido para extração (%s)", nome_arquivo)
        return {"origem": "nenhum", "erro": "texto vazio"}

    dados = {}

    if USAR_REGEX_PRIMEIRO:
        # Estratégia 1: nome da pasta
        nome_via_pasta = _buscar_nome_por_pasta(texto, nome_cliente_pasta)
        if nome_via_pasta:
            dados["nome"] = nome_via_pasta
            log.info("[%s] Nome confirmado via nome da pasta: %r", nome_arquivo, nome_via_pasta)

        # Estratégia 2: rótulos (preenche o que ainda estiver faltando,
        # nome incluso — se por algum motivo o nome da pasta não bateu
        # mas o rótulo achar algo válido, mantemos o rótulo como reforço)
        dados_rotulo = _buscar_por_rotulo(texto)
        for k, v in dados_rotulo.items():
            if v and not dados.get(k):
                dados[k] = v

        if _campos_completos(dados):
            log.info("[%s] Campos extraídos via regex (sem IA)", nome_arquivo)
            dados["origem"] = "regex"
            return dados
        else:
            log.info(
                "[%s] Regex não encontrou todos os campos obrigatórios — acionando IA local",
                nome_arquivo,
            )

    dados_ia = extrair_via_ollama(texto)

    dados_final = dict(dados_ia)
    for k, v in dados.items():
        if v:
            dados_final[k] = v
    dados_final["origem"] = "ia" if not dados else "regex+ia"
    return dados_final
