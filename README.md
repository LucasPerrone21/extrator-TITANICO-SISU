# SISU 2026 — Extração & Busca de E-mails

Ferramenta com interface gráfica para extrair os dados dos classificados do SISU 2026 a partir do PDF oficial e buscar automaticamente os e-mails de cada candidato no Google Contacts Directory.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/Licença-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20Mac-lightgrey?style=flat-square)

---

## Funcionalidades

- **Extração de PDF** — lê o PDF oficial do SISU e exporta todos os registros para uma planilha `.xlsx` com as colunas: `CURSO`, `NOME`, `INSCRIÇÃO`, `COTA CLASS`, `ESCORE`, `ANO` e `SEMESTRE`
- **Busca de e-mails** — pesquisa cada nome da planilha no Google Contacts Directory e preenche automaticamente a coluna `Email`
- **Interface gráfica** — aplicação desktop com duas abas, barra de progresso, contadores em tempo real e log de execução
- **Retomada automática** — se a execução for interrompida, o script retoma de onde parou na próxima vez
- **Anti-bloqueio** — delays aleatórios e pausas periódicas para evitar bloqueio pelo Google
- **Salva progresso a cada 50 registros** — nenhum dado é perdido em caso de falha

---

## Pré-requisitos

- Python 3.10 ou superior
- Google Chrome instalado na máquina
- Conta Google com acesso ao [Google Contacts Directory](https://contacts.google.com/directory)

---

## Instalação

Clone o repositório e instale as dependências:

```bash
git clone https://github.com/LucasPerrone21/extrator-TITANICO-SISU.git
cd extrator-TITANICO-SISU
pip install -r requirements.txt
```

### `requirements.txt`

```
selenium
webdriver-manager
pandas
openpyxl
beautifulsoup4
pdfplumber
```

---

## Como usar

### 1. Inicie a aplicação

```bash
python main.py
```

### 2. Aba "Extrair PDF"

1. Clique em **`…`** e selecione o PDF oficial do SISU
2. Defina o caminho da planilha de saída (`.xlsx`)
3. Clique em **EXTRAIR PDF**
4. Aguarde o processamento — a barra de progresso indica página a página

O resultado será uma planilha com todos os classificados pronta para a próxima etapa.

### 3. Aba "Buscar E-mails"

1. Selecione a planilha gerada na etapa anterior
2. Defina o nome do arquivo de saída
3. Clique em **INICIAR BUSCA**
4. O Chrome abrirá automaticamente — faça login na sua conta Google
5. Após logar, clique no banner **"Já fiz login →"** na aplicação
6. A busca iniciará automaticamente

Você pode clicar em **PARAR** a qualquer momento. O progresso é salvo e pode ser retomado depois.

---

## Estrutura do projeto

```
extrator-TITANICO-SISU/
├── main.py               # Interface gráfica unificada
├── requirements.txt
└── README.md
```

---

## Gerando um executável

### Windows

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "SISU_2026" main.py
```

O executável será gerado em `dist/SISU_2026.exe`.

### Linux / WSL

```bash
pip install pyinstaller
pyinstaller --onefile --name "SISU_2026" main.py
```

O executável será gerado em `dist/SISU_2026`.

> **Atenção:** o executável gerado funciona apenas no sistema operacional onde foi compilado. Para gerar um `.exe` para Windows, execute o PyInstaller no Windows.

---

## Observações

- O Google Chrome precisa estar instalado — o ChromeDriver é gerenciado automaticamente pelo `webdriver-manager`
- A busca de e-mails depende do **Google Contacts Directory** da sua organização. Contas pessoais podem não ter acesso ao diretório
- O tempo estimado para processar ~3.400 registros é de **35 a 45 minutos** com a versão otimizada (espera reativa ao DOM)
- Um arquivo de log (`buscar_emails.log`) é gerado na mesma pasta durante a busca

---

## Aviso legal

Esta ferramenta foi desenvolvida para fins acadêmicos e institucionais. Use de forma responsável e em conformidade com os termos de serviço do Google e a legislação vigente de proteção de dados (LGPD).
