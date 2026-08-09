"""
Agente de Documentos da Corretora — ponto de entrada.

Uso:
    python main.py
        Usa a pasta `entrada/` (dentro do projeto) como pasta de clientes.

    python main.py "C:\\Caminho\\Para\\Seus\\Clientes"
        Usa a pasta informada diretamente.

Tudo roda localmente — nenhum dado sai da sua máquina.
"""

import sys
import time
from pathlib import Path

from config import PASTA_ENTRADA, ARQUIVO_EXCEL_SAIDA
from scanner import escanear_clientes
from leitor_pdf import extrair_texto
from ocr import extrair_texto_via_ocr
from extrator_campos import extrair_campos
from exportador_excel import exportar
from senha_pdf import PDFSenhaError
from logger import get_logger

log = get_logger("main")


def processar_arquivo(cliente: str, ano: str, caminho_arquivo: Path) -> dict:
    base = {
        "cliente": cliente,
        "ano": ano,
        "arquivo": caminho_arquivo.name,
        "caminho_completo": str(caminho_arquivo),
    }

    try:
        texto = extrair_texto(caminho_arquivo)
    except PDFSenhaError as e:
        log.warning("[%s] PDF protegido, senha não encontrada: %s", cliente, e)
        resultado = dict(base)
        resultado.update({"status": "erro", "origem": "-", "erro_detalhe": "PDF protegido por senha"})
        return resultado

    if not texto:
        log.info("[%s] Sem texto digital, tentando OCR: %s", cliente, caminho_arquivo.name)
        texto = extrair_texto_via_ocr(caminho_arquivo)

    if not texto:
        log.error("[%s] Não foi possível extrair texto (nem digital, nem OCR): %s",
                   cliente, caminho_arquivo.name)
        resultado = dict(base)
        resultado.update({"status": "erro", "origem": "-", "erro_detalhe": "Não foi possível extrair texto do PDF"})
        return resultado

    # Passamos o nome do cliente (nome da pasta) para o extrator, que usa
    # isso como a fonte mais confiável para confirmar o campo "nome".
    dados = extrair_campos(texto, nome_arquivo=caminho_arquivo.name, nome_cliente_pasta=cliente)

    if dados.get("erro"):
        mapa_erros = {
            "ollama_offline": "Ollama não está rodando (verifique 'ollama serve')",
            "timeout": "Ollama demorou demais para responder (timeout)",
            "http_error": "Erro de comunicação com o Ollama",
            "texto vazio": "Texto vazio extraído do PDF",
        }
        resultado = dict(base)
        resultado["status"] = "erro"
        resultado["origem"] = dados.get("origem", "-")
        resultado["erro_detalhe"] = mapa_erros.get(dados["erro"], dados["erro"])
        return resultado

    status = "ok" if all(dados.get(c) for c in ["nome", "data_nascimento"]) else "parcial"

    resultado = dict(base)
    resultado.update(dados)
    resultado["status"] = status
    if status == "parcial":
        resultado["erro_detalhe"] = "Um ou mais campos não foram encontrados"
    return resultado


def main():
    inicio = time.time()

    print("=" * 60)
    print("  Agente de Documentos da Corretora")
    print("  Processamento 100% local (Ollama)")
    print("=" * 60)

    if len(sys.argv) > 1:
        pasta_clientes = Path(sys.argv[1])
    else:
        pasta_clientes = PASTA_ENTRADA

    if not pasta_clientes.exists():
        print(f"\nERRO: a pasta informada não existe: {pasta_clientes}")
        sys.exit(1)

    print(f"  Pasta de clientes: {pasta_clientes}\n")

    log.info("Iniciando escaneamento de %s", pasta_clientes)
    clientes_encontrados = escanear_clientes(pasta_clientes)

    if not clientes_encontrados:
        print(f"\nNenhum cliente encontrado em: {pasta_clientes}")
        sys.exit(1)

    resultados = []
    total_arquivos = sum(len(c.arquivos_apolice) for c in clientes_encontrados)
    processados = 0

    for cliente_info in clientes_encontrados:
        if cliente_info.erro:
            resultados.append({
                "cliente": cliente_info.cliente,
                "ano": cliente_info.ano_encontrado or "-",
                "arquivo": "-",
                "caminho_completo": "-",
                "status": "erro",
                "origem": "-",
                "erro_detalhe": cliente_info.erro,
            })
            continue

        for arquivo in cliente_info.arquivos_apolice:
            processados += 1
            print(f"[{processados}/{total_arquivos}] Processando: "
                  f"{cliente_info.cliente} / {arquivo.name}")
            resultado = processar_arquivo(
                cliente_info.cliente, cliente_info.ano_encontrado, arquivo
            )
            resultados.append(resultado)

    caminho_final = exportar(resultados, ARQUIVO_EXCEL_SAIDA)

    ok = sum(1 for r in resultados if r.get("status") == "ok")
    parcial = sum(1 for r in resultados if r.get("status") == "parcial")
    erro = sum(1 for r in resultados if r.get("status") == "erro")
    tempo_total = time.time() - inicio

    print("\n" + "=" * 60)
    print("  RESUMO")
    print("=" * 60)
    print(f"  Clientes encontrados:  {len(clientes_encontrados)}")
    print(f"  Documentos processados: {len(resultados)}")
    print(f"    OK (completo):        {ok}")
    print(f"    Parcial (campo faltando): {parcial}")
    print(f"    Erro:                 {erro}")
    print(f"  Tempo total:           {tempo_total:.1f}s")
    print(f"  Excel gerado em:       {caminho_final}")
    print("=" * 60)


if __name__ == "__main__":
    main()
