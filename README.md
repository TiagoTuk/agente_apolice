# 🤖 Agente de IA para Extração de Dados de Apólices

Automação de extração de dados de apólices de seguro em PDF, usando uma
estratégia híbrida de **regex + IA generativa local**, desenvolvida para
resolver um problema real de uma corretora de seguros.

---

## 📌 O problema

A corretora onde trabalho tem centenas de clientes, cada um com pastas de
apólices acumuladas ao longo de vários anos — sem um padrão único de
organização entre eles. Para gerar um relatório simples com nome e data
de nascimento de cada cliente, alguém precisava abrir manualmente cada
PDF, um por um. Com ~200 clientes e documentos de até 10 anos de
histórico, esse processo levava dias de trabalho manual repetitivo.

## 💡 A solução

Um agente que percorre a estrutura de pastas automaticamente,
encontra o documento mais recente de cada cliente, extrai os campos
necessários e gera uma planilha Excel consolidada — sem exigir nenhum
padrão fixo de organização de arquivos.

**Resultado:** um processo que levava dias de trabalho manual passou a
rodar sozinho, em background, na própria máquina.

## 🏗️ Arquitetura

```
PDF do cliente
     │
     ▼
┌─────────────────┐
│  1. Scanner      │  Localiza a pasta do ano mais recente de cada
│                  │  cliente, com busca recursiva — não depende de
│                  │  uma estrutura fixa de subpastas.
└────────┬─────────┘
         ▼
┌─────────────────┐
│  2. Leitura      │  PDF digital → extração direta de texto
│                  │  PDF escaneado → OCR (Tesseract)
│                  │  PDF protegido → tentativa automática de senha
└────────┬─────────┘
         ▼
┌─────────────────────────────────────────────┐
│  3. Extração de campos (estratégia híbrida)   │
│                                                │
│  a) Nome da pasta do cliente é buscado         │
│     diretamente no texto — a fonte mais         │
│     confiável, já que a pasta sempre tem o       │
│     nome real do cliente (PF ou PJ)               │
│  b) Regex de rótulos comuns (Segurado, Titular,    │
│     Data de Nascimento...) para o que ainda falta   │
│  c) Só se as duas primeiras não resolverem, cai      │
│     para um LLM local (Ollama) — mais lento, usado    │
│     como último recurso                                │
└────────┬───────────────────────────────────────────────┘
         ▼
┌─────────────────┐
│  4. Excel final  │  Relatório consolidado com status de cada
│                  │  documento (ok / parcial / erro) e o motivo
│                  │  de qualquer falha, para auditoria rápida.
└──────────────────┘
```

## 🔑 Decisões técnicas que valem destacar

- **Tudo roda 100% local.** Os documentos contêm dados pessoais de
  clientes (nome, CPF, data de nascimento), então usar uma API de IA
  na nuvem levantaria questões de LGPD. A solução usa
  [Ollama](https://ollama.com) para rodar um LLM inteiramente na
  máquina — nenhum dado sai do ambiente da corretora.

- **Estratégia híbrida em vez de "IA em tudo".** A maior parte dos
  documentos é resolvida só com regex, sem precisar do modelo de IA.
  A IA é usada apenas como fallback, para os casos em que o layout do
  documento foge do padrão esperado. Isso reduz drasticamente o tempo
  de processamento de um lote grande de documentos.

- **Robustez a estruturas de pastas inconsistentes.** Diferentes
  clientes têm diferentes níveis de subpastas (por produto, por ano,
  por veículo...). O scanner faz uma busca recursiva por qualquer
  pasta de ano existente, em vez de assumir uma estrutura fixa —
  incluindo o caso de clientes novos, sem histórico de renovação
  ainda.

- **Tratamento de exceções do mundo real.** PDFs protegidos por senha
  (com tentativa automática usando variações do CPF do cliente),
  documentos escaneados sem texto selecionável, e até ajuste de
  parâmetros por seguradora (ex: uma seguradora específica exige mais
  texto enviado ao modelo, porque os dados do segurado aparecem só a
  partir da página 3 do documento).

## 🛠️ Tecnologias

| Categoria | Ferramenta |
|---|---|
| Linguagem | Python 3.12+ |
| Leitura de PDF | PyMuPDF (fitz) |
| OCR | Tesseract + pytesseract |
| IA Generativa | Ollama (LLM local) |
| Exportação | OpenPyXL |
| Extração de padrões | Regex |

## 📊 Como funciona na prática

1. O agente escaneia a pasta de clientes, encontrando o documento mais
   recente de cada um.
2. Extrai o texto (digital ou via OCR).
3. Tenta resolver nome e data de nascimento via regex — usando o nome
   da pasta do cliente como fonte de verdade sempre que possível.
4. Só recorre à IA local quando a regex não é suficiente.
5. Gera um Excel com o resultado de cada cliente, incluindo uma coluna
   de diagnóstico para qualquer falha (documento protegido por senha,
   estrutura de pasta inesperada, etc.), facilitando a correção manual
   pontual dos casos que precisam de atenção humana.

## 🚀 Como rodar

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

python -m pip install -r requirements.txt

# Baixe o Ollama (https://ollama.com) e um modelo:
ollama pull llama3.2

python main.py "caminho/para/pasta/de/clientes"
```

Veja o [manual de instalação completo](./README_INSTALACAO.md) para o
passo a passo detalhado (incluindo configuração do Tesseract OCR).

## 📁 Estrutura do projeto

```
agente_apolices/
├── main.py                 # Ponto de entrada
├── config.py                # Configurações (campos, timeouts, etc.)
├── scanner.py                # Localiza os documentos nas pastas
├── leitor_pdf.py              # Leitura de PDFs digitais
├── ocr.py                      # OCR para PDFs escaneados
├── senha_pdf.py                 # Tratamento de PDFs protegidos
├── extrator_campos.py            # Estratégia híbrida de extração
├── extrator_ia.py                  # Integração com Ollama
└── exportador_excel.py              # Geração do relatório final
```

## 🔮 Próximos passos

Esse projeto começou resolvendo um problema pontual (nome e data de
nascimento), mas a arquitetura já foi pensada para crescer. Os
próximos passos incluem:

- **Extrair mais campos das apólices**: vigência, valor líquido e
  bruto do seguro, CPF, número da apólice, seguradora, entre outros —
  a lista de campos é configurável, então adicionar um campo novo não
  exige reescrever a lógica de extração.
- **Automatizar outros processos internos da corretora** a partir
  desses dados adicionais, como conciliação de comissões e controle de
  vencimentos/renovações.
- **Painel de acompanhamento** para visualizar o progresso do
  processamento em lote e revisar rapidamente os casos que precisam de
  atenção manual.
- **Reduzir ainda mais a dependência da IA**, ampliando os padrões de
  regex conforme novos layouts de seguradoras forem sendo mapeados.

## 🔒 Sobre privacidade

Este repositório contém apenas o código-fonte. Nenhum dado real de
cliente, apólice ou documento é incluído aqui — todos os exemplos e
capturas de tela usam dados fictícios.

## 👤 Sobre mim

Esse projeto nasceu de uma necessidade real do meu trabalho como
administrador em uma corretora de seguros, enquanto migro de carreira
para a área de Dados. Mais projetos no meu
[portfólio](https://tiagotuk.github.io/portfolio_projetos/) e
[LinkedIn](https://www.linkedin.com/in/tiago-gomes-de-barros-953775196/).
