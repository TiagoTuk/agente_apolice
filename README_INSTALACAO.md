# Agente de Documentos da Corretora

Extrai automaticamente Nome e Data de Nascimento de apólices em PDF,
percorrendo a pasta de clientes recursivamente. Roda **100% local**
(nenhum dado sai da sua máquina) — usa Ollama para os casos em que a
extração simples não é suficiente.

## 1. Pré-requisitos

### Python
```
python --version
```

### Tesseract OCR (para PDFs escaneados)
- **Windows**: instalador em https://github.com/UB-Mannheim/tesseract/wiki
  (marque o pacote de idioma **Portuguese**)
- **Mac**: `brew install tesseract tesseract-lang`
- **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-por`

Se `tesseract --version` não funcionar após instalar, adicione esta linha
no início de `ocr.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### Ollama (IA local)
1. Instale em https://ollama.com/download
2. Baixe o modelo: `ollama pull llama3.2`
   (modelo leve, recomendado para máquinas com 8-16GB de RAM; se tiver
   16GB+ sobrando, pode trocar para `llama3.1` em `config.py` para mais
   precisão)
3. Confirme que está rodando: acesse http://localhost:11434 (deve mostrar "Ollama is running")

> **Dica de performance**: antes de rodar o agente em lote, rode
> `ollama run llama3.2` uma vez manualmente e mande qualquer pergunta.
> Isso "esquenta" o modelo na memória.

## 2. Instalação do projeto

```bash
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

python -m pip install -r requirements.txt
```

## 3. Como usar

**Opção A — apontando direto para a pasta onde os clientes já estão** (recomendado):
```bash
python main.py "C:\Caminho\Para\Seus\Clientes"
```

**Opção B — copiando os clientes para dentro do projeto:**
Coloque as pastas dos clientes em `entrada/` e rode sem argumento:
```bash
python main.py
```

O resultado final aparece em `resultado/apolices.xlsx`, e o log
detalhado fica em `logs/execucao.log`.

## 4. Como a extração funciona (3 estratégias, em ordem)

1. **Nome da pasta do cliente**: como a pasta é sempre nomeada com o
   nome do cliente (PF ou PJ), o agente procura esse nome diretamente
   no texto do PDF. Se encontrar, usa com alta confiança — não depende
   de adivinhar qual rótulo a seguradora usou. Também tolera anotações
   extras no nome da pasta (ex: "ADAUTO DE SOUZA SANTOS -SOGRO
   IR.GELSON" vira "ADAUTO DE SOUZA SANTOS" antes da busca).
2. **Rótulos comuns** ("Segurado:", "Titular:", "Nome Completo:",
   "Data de Nascimento:") — usado quando a estratégia 1 não encontra
   nada, ou para achar a data de nascimento (que não tem uma "fonte
   confiável" equivalente ao nome da pasta).
3. **IA local (Ollama)** — usado só quando as duas primeiras não
   resolvem todos os campos obrigatórios. É o mais lento, então quanto
   mais as estratégias 1 e 2 resolverem sozinhas, mais rápido o
   processamento do lote inteiro.

## 5. Estrutura do projeto

```
Agente_Apolices/
├── main.py                 # Ponto de entrada — roda tudo
├── config.py                # Configurações (campos a extrair, timeout, etc.)
├── scanner.py                # Fase 1 — encontra as apólices nas pastas
├── leitor_pdf.py              # Fase 2a — lê PDFs digitais
├── ocr.py                      # Fase 2b — OCR para PDFs escaneados
├── senha_pdf.py                 # Trata PDFs protegidos por senha
├── extrator_campos.py            # Fase 3 — nome da pasta > rótulo > IA
├── extrator_ia.py                  # Conversa com o Ollama local
├── exportador_excel.py              # Gera o Excel final
├── requirements.txt
├── entrada/                          # (opcional) clientes de teste
├── resultado/                          # Excel final aparece aqui
└── logs/                                # Logs de execução
```

## 6. Lendo o Excel de resultado

Colunas fixas: **Cliente, Ano, Arquivo, Caminho completo, Origem, Status, Erro Detalhe**,
seguidas de Nome e Data Nascimento.

- **Status = ok**: os dois campos foram encontrados.
- **Status = parcial**: só um dos dois campos foi encontrado.
- **Status = erro**: nada foi extraído — confira **Erro Detalhe**.
- **Origem = regex**: achou sem precisar de IA (mais rápido/confiável).
- **Origem = regex+ia** ou **ia**: precisou do Ollama para algum campo.

## 7. Sobre a busca de pasta de ano

O scanner detecta automaticamente **qualquer** subpasta com nome de ano
(4 dígitos, ex: "2019", "2025") e usa a mais recente que existir de
fato para aquele cliente — não fica travado nos últimos 2 anos.

Se um cliente não tiver NENHUMA subpasta de ano (comum em clientes
novos, cuja primeira apólice ainda não passou por renovação), o agente
procura a apólice direto na pasta raiz do cliente.

## 8. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| "Nenhuma pasta de ano encontrada" mesmo tendo pastas | Confira o log — ele lista as subpastas reais encontradas para esse cliente, até 3 níveis. |
| Timeout do Ollama | Modelo grande demais para o hardware, ou cold start. Aumente `OLLAMA_TIMEOUT` em `config.py`, use um modelo mais leve (`llama3.2`), ou rode `ollama run <modelo>` manualmente antes para pré-carregar. |
| Erro HTTP 500 do Ollama | Geralmente falta de memória RAM para o modelo escolhido. Troque para um modelo menor em `config.py` (`OLLAMA_MODELO`). |
| Nome extraído é um trecho de cláusula, não um nome de pessoa | Corrigido nesta versão — regex exige rótulo no início de linha e valida o texto capturado; além disso, a estratégia de nome-da-pasta praticamente elimina esse risco quando funciona. |

## 9. Adicionando novos campos (CPF, vigência, etc.)

Edite o dicionário `CAMPOS_EXTRACAO` em `config.py`. O prompt enviado
ao Ollama é montado automaticamente a partir dessa lista.
