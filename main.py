import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import logging
import queue
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# ──────────────────────────────────────────────────────────────
# Paleta e constantes visuais
# ──────────────────────────────────────────────────────────────
BG          = "#0f1117"
BG_CARD     = "#181c27"
BG_INPUT    = "#1e2333"
ACCENT      = "#f2a900"
ACCENT_DIM  = "#c58c07"
SUCCESS     = "#3ecf8e"
WARNING     = "#f5a623"
DANGER      = "#f25f5c"
TEXT        = "#e8eaf0"
TEXT_DIM    = "#6b7280"
BORDER      = "#2a3045"

FONT_TITLE  = ("Georgia", 22, "bold")
FONT_LABEL  = ("Courier New", 10)
FONT_MONO   = ("Courier New", 9)
FONT_BTN    = ("Courier New", 10, "bold")
FONT_BADGE  = ("Courier New", 8, "bold")

# Palavras que identificam a linha de cabeçalho da tabela.
# Diferentes edições do PDF do SISU/UFBA usam nomes de coluna diferentes
# para a primeira coluna: "MUNICÍPIO" (chamada regular) ou "CURSO" (outras chamadas).
HEADER_KEYWORDS = {"MUNICIPIO", "CURSO"}

# ──────────────────────────────────────────────────────────────
# Navegadores suportados e gerenciamento de perfis persistentes
# ──────────────────────────────────────────────────────────────
NAVEGADORES = [
    "Google Chrome",
    "Mozilla Firefox",
    "Microsoft Edge",
    "Brave",
]


def normalizar_chave_navegador(nome: str) -> str:
    n = (nome or "").strip().lower()
    if "firefox" in n:
        return "firefox"
    if "edge" in n:
        return "edge"
    if "brave" in n:
        return "brave"
    return "chrome"


def get_profile_dir(navegador: str) -> Path:
    """Retorna o diretório de perfil persistente para o navegador especificado."""
    chave = normalizar_chave_navegador(navegador)
    base = Path(__file__).resolve().parent
    if chave == "chrome":
        return base / "chrome_profile"
    elif chave == "firefox":
        return base / "firefox_profile"
    elif chave == "edge":
        return base / "edge_profile"
    elif chave == "brave":
        return base / "brave_profile"
    return base / f"{chave}_profile"


# Mantido para retrocompatibilidade
PROFILE_DIR = get_profile_dir("chrome")


def sessao_existe(navegador: str) -> bool:
    """Verifica se há dados salvos de perfil para o navegador."""
    p = get_profile_dir(navegador)
    return p.exists() and any(p.iterdir())


def sessao_chrome_existe() -> bool:
    """Verifica se há dados salvos de perfil do Chrome (retrocompatibilidade)."""
    return sessao_existe("chrome")


def limpar_sessao(navegador: str):
    """Remove o diretório de perfil do navegador para deslogar/trocar de conta."""
    import shutil
    p = get_profile_dir(navegador)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def limpar_sessao_chrome():
    """Remove o diretório do perfil do Chrome (retrocompatibilidade)."""
    limpar_sessao("chrome")


def detectar_navegador(navegador: str) -> tuple[bool, str]:
    """Verifica se o navegador está instalado no sistema operacional e retorna (instalado, caminho)."""
    import os
    import platform
    import shutil

    chave = normalizar_chave_navegador(navegador)
    sistema = platform.system()

    if chave == "chrome":
        if sistema == "Linux":
            for b in ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "/opt/google/chrome/google-chrome"]:
                if b.startswith("/") and Path(b).exists():
                    return True, str(Path(b).resolve())
                p = shutil.which(b)
                if p:
                    return True, p
        elif sistema == "Windows":
            candidatos = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            for cand in candidatos:
                if Path(cand).exists():
                    return True, cand
            p = shutil.which("chrome")
            if p:
                return True, p
        elif sistema == "Darwin":
            p = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            if p.exists():
                return True, str(p)
            p = shutil.which("google-chrome")
            if p:
                return True, p

    elif chave == "firefox":
        if sistema == "Linux":
            for b in ["firefox", "/usr/bin/firefox"]:
                if b.startswith("/") and Path(b).exists():
                    return True, str(Path(b).resolve())
                p = shutil.which(b)
                if p:
                    return True, p
        elif sistema == "Windows":
            candidatos = [
                os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
            ]
            for cand in candidatos:
                if Path(cand).exists():
                    return True, cand
            p = shutil.which("firefox")
            if p:
                return True, p
        elif sistema == "Darwin":
            p = Path("/Applications/Firefox.app/Contents/MacOS/firefox")
            if p.exists():
                return True, str(p)
            p = shutil.which("firefox")
            if p:
                return True, p

    elif chave == "edge":
        if sistema == "Linux":
            for b in ["microsoft-edge-stable", "microsoft-edge", "/opt/microsoft/msedge/msedge"]:
                if b.startswith("/") and Path(b).exists():
                    return True, str(Path(b).resolve())
                p = shutil.which(b)
                if p:
                    return True, p
        elif sistema == "Windows":
            candidatos = [
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            ]
            for cand in candidatos:
                if Path(cand).exists():
                    return True, cand
            p = shutil.which("msedge")
            if p:
                return True, p
        elif sistema == "Darwin":
            p = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
            if p.exists():
                return True, str(p)
            p = shutil.which("microsoft-edge")
            if p:
                return True, p

    elif chave == "brave":
        if sistema == "Linux":
            for b in [
                "brave-browser", "brave-browser-stable", "brave",
                "/usr/bin/brave-browser", "/usr/bin/brave-browser-stable",
                "/opt/brave.com/brave/brave-browser", "/opt/brave.com/brave/brave",
            ]:
                if b.startswith("/") and Path(b).exists():
                    return True, str(Path(b).resolve())
                p = shutil.which(b)
                if p:
                    return True, p
        elif sistema == "Windows":
            candidatos = [
                os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ]
            for cand in candidatos:
                if Path(cand).exists():
                    return True, cand
            p = shutil.which("brave")
            if p:
                return True, p
        elif sistema == "Darwin":
            p = Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
            if p.exists():
                return True, str(p)
            p = shutil.which("brave")
            if p:
                return True, p

    return False, ""


def obter_navegador_padrao() -> str:
    """Retorna o primeiro navegador detectado no sistema, ou 'Google Chrome' se nenhum for detectado."""
    for nav in NAVEGADORES:
        ok, _ = detectar_navegador(nav)
        if ok:
            return nav
    return NAVEGADORES[0]



def _normalizar(texto: str) -> str:
    """Remove acentos e espaços extras, deixa em maiúsculas, para comparação robusta."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return texto.strip().upper()


def _linha_e_cabecalho(row) -> bool:
    if not row or not row[0]:
        return False
    return _normalizar(row[0]) in HEADER_KEYWORDS

# ──────────────────────────────────────────────────────────────
# Fila de log (comunicação thread → UI)
# ──────────────────────────────────────────────────────────────
log_queue: queue.Queue = queue.Queue()


class QueueHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(self.format(record))


# ──────────────────────────────────────────────────────────────
# Lógica de extração PDF (roda em thread)
# ──────────────────────────────────────────────────────────────
def detectar_colunas_pdf(pdf_path: str, max_paginas: int = 5):
    """Lê apenas as primeiras páginas do PDF para descobrir rapidamente
    os nomes das colunas (linha de cabeçalho), sem processar o arquivo inteiro.
    O cabeçalho pode aparecer em qualquer uma das primeiras páginas
    (algumas edições do PDF só imprimem o cabeçalho uma única vez)."""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_paginas]:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if _linha_e_cabecalho(row):
                            return [str(c).strip() if c else "" for c in row]
    except Exception:
        pass
    return []


def extrair_pdf(pdf_path: str, output_path: str, colunas_desejadas: str, callback_progresso, callback_fim):
    try:
        import pdfplumber
        log = logging.getLogger("extrator")

        all_rows = []
        header = None
        linhas_descartadas = 0

        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                callback_progresso(i, total, f"Página {i}/{total}")
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row or not any(row):
                            continue

                        if _linha_e_cabecalho(row):
                            header = row
                            continue

                        # Ignora qualquer linha antes de o cabeçalho ser
                        # encontrado (ex: texto de introdução/instruções do
                        # PDF, que aparece antes da primeira tabela real).
                        if header is None:
                            continue

                        # Ignora linhas com número de colunas diferente do
                        # cabeçalho (lixo de formatação/tabelas mal detectadas).
                        if len(row) != len(header):
                            linhas_descartadas += 1
                            continue

                        all_rows.append(row)

        if linhas_descartadas:
            log.info(f"⚠ {linhas_descartadas} linha(s) descartada(s) por não corresponder ao formato do cabeçalho.")

        if not header or not all_rows:
            callback_fim(False, "Nenhuma tabela encontrada no PDF.")
            return

        df = pd.DataFrame(all_rows, columns=header)

        # ESCORE vem no formato "679,71" -> converte para número
        if "ESCORE" in df.columns:
            df["ESCORE"] = pd.to_numeric(
                df["ESCORE"].astype(str).str.replace(",", "."), errors="coerce"
            )

        # As colunas ANO / SEMESTRE / INSCRICAO não existem no modelo de PDF
        # do SISU/UFBA (chamada regular). Se um dia aparecerem, tratamos aqui:
        if "ANO" in df.columns:
            df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce").astype("Int64")
        if "SEMESTRE" in df.columns:
            df["SEMESTRE"] = pd.to_numeric(
                df["SEMESTRE"].astype(str).str.extract(r"(\d+)", expand=False), errors="coerce"
            ).astype("Int64")
        if "INSCRICAO" in df.columns:
            df["INSCRICAO"] = df["INSCRICAO"].astype(str)

        # --- FILTRAR COLUNAS DESEJADAS ---
        if colunas_desejadas:
            cols_desejadas = [c.strip().upper() for c in colunas_desejadas.split(",") if c.strip()]
            if cols_desejadas:
                cols_df_upper = {col.upper(): col for col in df.columns}
                cols_filtrar = []
                for col_des in cols_desejadas:
                    if col_des in cols_df_upper:
                        cols_filtrar.append(cols_df_upper[col_des])
                    else:
                        log.warning(f"Coluna desejada não encontrada no PDF: {col_des}")

                if cols_filtrar:
                    df = df[cols_filtrar]

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Classificados")
            ws = writer.sheets["Classificados"]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

        log.info(f"✔ {len(df)} registros extraídos → {output_path}")
        callback_fim(True, f"{len(df)} registros extraídos com sucesso.")

    except Exception as e:
        callback_fim(False, str(e))


# ──────────────────────────────────────────────────────────────
# Lógica de busca de e-mails (roda em thread)
# ──────────────────────────────────────────────────────────────
XPATH_INPUT    = '//*[@id="gb"]/div[2]/div[2]/div[2]/form/div/div/div/div/div/div[1]/input[2]'
XPATH_RESULT   = '//*[@id="gb"]/div[2]/div[2]/div[2]/form/div/div/div/div/div/div[2]'
CLASS_EMAIL    = "mf6tRb"

WAIT_TIMEOUT   = 0.2   # tempo de espera para elementos ficarem visíveis
DELAY_PESQUISA = 1.2   # pausa após digitar, aguarda resultado carregar
DELAY_ENTRE    = 0.3   # pausa entre cada busca
SALVAR_A_CADA  = 50

_stop_flag = threading.Event()


def extrair_email_html(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("div", class_=CLASS_EMAIL)
    if tag:
        return tag.text.strip().replace("‒", "").strip()
    return None


def iniciar_driver(navegador: str, profile_dir: Path, log):
    """Inicializa e retorna o driver Selenium para o navegador solicitado,
    configurado com perfil persistente para manter a sessão ativa."""
    from selenium import webdriver
    chave = normalizar_chave_navegador(navegador)
    profile_dir.mkdir(parents=True, exist_ok=True)

    if chave == "chrome":
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager

        opcoes = ChromeOptions()
        opcoes.add_argument(f"--user-data-dir={profile_dir.resolve()}")
        opcoes.add_argument("--disable-notifications")

        try:
            return webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=opcoes
            )
        except Exception as e:
            log.warning(f"WebDriverManager falhou ({e}). Tentando Selenium Manager...")
            return webdriver.Chrome(options=opcoes)

    elif chave == "firefox":
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager

        opcoes = FirefoxOptions()
        opcoes.add_argument("-profile")
        opcoes.add_argument(str(profile_dir.resolve()))
        opcoes.set_preference("dom.webnotifications.enabled", False)

        try:
            return webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()),
                options=opcoes
            )
        except Exception as e:
            log.warning(f"GeckoDriverManager falhou ({e}). Tentando Selenium Manager...")
            return webdriver.Firefox(options=opcoes)

    elif chave == "edge":
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager

        opcoes = EdgeOptions()
        opcoes.add_argument(f"--user-data-dir={profile_dir.resolve()}")
        opcoes.add_argument("--disable-notifications")

        try:
            return webdriver.Edge(
                service=EdgeService(EdgeChromiumDriverManager().install()),
                options=opcoes
            )
        except Exception as e:
            log.warning(f"EdgeChromiumDriverManager falhou ({e}). Tentando Selenium Manager...")
            return webdriver.Edge(options=opcoes)

    elif chave == "brave":
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        import subprocess
        import socket

        ok_brave, caminho_brave = detectar_navegador("brave")
        if not ok_brave or not caminho_brave:
            raise FileNotFoundError("O executável do Brave não foi encontrado no sistema.")

        # Obtém uma porta livre para o DevTools para evitar fechamento do Brave no Linux
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]

        cmd = [
            caminho_brave,
            f"--user-data-dir={profile_dir.resolve()}",
            f"--remote-debugging-port={porta}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-notifications",
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

        opcoes = ChromeOptions()
        opcoes.add_experimental_option("debuggerAddress", f"127.0.0.1:{porta}")

        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=opcoes
            )
        except Exception as e:
            log.warning(f"ChromeDriverManager falhou ({e}). Tentando Selenium Manager nativo...")
            try:
                driver = webdriver.Chrome(options=opcoes)
            except Exception as e2:
                proc.terminate()
                raise e2

        driver._brave_proc = proc
        return driver

    raise ValueError(f"Navegador não suportado: {navegador}")


def buscar_emails(xlsx_path: str, output_path: str, coluna_nome: str,
                  callback_progresso, callback_status,
                  callback_fim, evento_login_ok: threading.Event,
                  navegador: str = "Google Chrome"):
    log = logging.getLogger("buscador")
    driver = None

    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException, NoSuchElementException,
            StaleElementReferenceException, WebDriverException,
        )

        coluna_nome = (coluna_nome or "").strip()
        if not coluna_nome:
            callback_fim(False, "Nenhuma coluna de nome selecionada.")
            return

        # Carrega dados (retoma progresso se arquivo de saída já existir)
        if Path(output_path).exists():
            df = pd.read_excel(output_path, dtype={coluna_nome: str})
            log.info(f"Retomando progresso de: {output_path}")
        else:
            df = pd.read_excel(xlsx_path, dtype={coluna_nome: str})
            df["Email"] = None
            df["Status_Busca"] = None

        if coluna_nome not in df.columns:
            callback_fim(False, f"A coluna '{coluna_nome}' não existe na planilha.")
            return

        pendentes = df[df["Status_Busca"].isna()].index.tolist()
        total_pendentes = len(pendentes)

        if not pendentes:
            callback_fim(True, "Todos os registros já foram processados.")
            return

        log.info(f"Pendentes: {total_pendentes} | Já feitos: {len(df) - total_pendentes}")

        # Garante diretório de perfil persistente para o navegador escolhido
        profile_dir = get_profile_dir(navegador)
        log.info(f"Iniciando {navegador} com perfil em: {profile_dir.name}")

        try:
            driver = iniciar_driver(navegador, profile_dir, log)
        except WebDriverException as e:
            err_msg = str(e).lower()
            if "user data directory is already in use" in err_msg or "singletonlock" in err_msg or "already in use" in err_msg or "process is already using" in err_msg:
                callback_fim(False, f"O perfil do {navegador} já está em uso por outro processo. Feche todas as janelas do {navegador} e tente novamente.")
                return
            callback_fim(False, f"Falha ao iniciar {navegador}: {e}")
            return
        except Exception as e:
            callback_fim(False, f"Erro ao iniciar {navegador}: {e}")
            return

        driver.get("https://contacts.google.com/directory")
        time.sleep(2)

        url_atual = driver.current_url.lower()
        precisa_login = "accounts.google.com" in url_atual or "servicelogin" in url_atual or "signin" in url_atual

        if precisa_login:
            log.info(f"Login necessário no Google Contacts via {navegador}...")
            callback_status("aguardando_login")
            evento_login_ok.wait()  # UI vai setar esse evento quando usuário clicar "Já fiz login"

            if _stop_flag.is_set():
                callback_fim(False, "Cancelado pelo usuário.")
                return

            driver.get("https://contacts.google.com/directory")
            time.sleep(2)
            callback_status("logado")
        else:
            log.info(f"✔ Sessão Google ativa detectada no perfil do {navegador}! Continuando busca automaticamente...")
            callback_status("logado")

        encontrados = sem_email = erros = 0
        inicio = time.monotonic()
        posicao = 0

        for posicao, idx in enumerate(pendentes, start=1):
            if _stop_flag.is_set():
                break

            nome = str(df.at[idx, coluna_nome]).strip()

            # ETA
            if posicao > 1:
                seg_por = (time.monotonic() - inicio) / (posicao - 1)
                restante = seg_por * (total_pendentes - posicao)
                m, s = divmod(int(restante), 60)
                eta = f"{m}m {s:02d}s"
            else:
                eta = "..."

            callback_progresso(posicao, total_pendentes, nome, eta, encontrados, sem_email, erros)

            try:
                campo = WebDriverWait(driver, WAIT_TIMEOUT).until(
                    EC.visibility_of_element_located((By.XPATH, XPATH_INPUT))
                )
                campo.clear()
                campo.send_keys(nome)
                time.sleep(DELAY_PESQUISA)

                try:
                    resultado_html = WebDriverWait(driver, WAIT_TIMEOUT).until(
                        EC.visibility_of_element_located((By.XPATH, XPATH_RESULT))
                    ).get_attribute("outerHTML")
                    email = extrair_email_html(resultado_html)
                except TimeoutException:
                    email = None

                if email:
                    df.at[idx, "Email"] = email
                    df.at[idx, "Status_Busca"] = "encontrado"
                    encontrados += 1
                    log.info(f"✔ [{posicao}] {nome} → {email}")
                else:
                    df.at[idx, "Email"] = ""
                    df.at[idx, "Status_Busca"] = "nao_encontrado"
                    sem_email += 1

            except (TimeoutException, NoSuchElementException):
                df.at[idx, "Email"] = ""
                df.at[idx, "Status_Busca"] = "erro"
                erros += 1
                log.warning(f"✗ [{posicao}] Erro: {nome}")

            except (StaleElementReferenceException, WebDriverException) as e:
                df.at[idx, "Status_Busca"] = "erro"
                erros += 1
                log.error(f"WebDriver: {e}")
                try:
                    driver.get("https://contacts.google.com/directory")
                    time.sleep(2)
                except WebDriverException:
                    df.to_excel(output_path, index=False)
                    callback_fim(False, "Navegador inacessível. Progresso salvo.")
                    return

            if posicao % SALVAR_A_CADA == 0:
                df.to_excel(output_path, index=False)
                log.info(f"[salvo] {posicao} registros")

            time.sleep(DELAY_ENTRE)

        df.to_excel(output_path, index=False)
        total_tempo = time.monotonic() - inicio
        m, s = divmod(int(total_tempo), 60)
        if _stop_flag.is_set():
            msg = f"Busca interrompida. {posicao} registros processados | {encontrados} e-mails | Progresso salvo."
            callback_fim(False, msg)
        else:
            msg = f"{posicao} registros | {encontrados} e-mails | {m}m {s:02d}s"
            callback_fim(True, msg)

    except Exception as e:
        callback_fim(False, str(e))
    finally:
        if driver is not None:
            try:
                brave_proc = getattr(driver, "_brave_proc", None)
                driver.quit()
                if brave_proc is not None:
                    brave_proc.terminate()
                    try:
                        brave_proc.wait(timeout=2)
                    except Exception:
                        brave_proc.kill()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────────
# Widget: Painel de Log
# ──────────────────────────────────────────────────────────────
class LogPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_CARD, **kw)
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=BG_CARD)
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(header, text="LOG", font=FONT_BADGE, fg=TEXT_DIM, bg=BG_CARD).pack(side="left")
        tk.Button(
            header, text="limpar", font=FONT_BADGE, fg=TEXT_DIM, bg=BG_CARD,
            activebackground=BG_CARD, activeforeground=TEXT, relief="flat",
            cursor="hand2", command=self.clear
        ).pack(side="right")

        frame = tk.Frame(self, bg=BG_CARD)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.text = tk.Text(
            frame, bg="#0a0c12", fg="#9ca3b0", font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            insertbackground=ACCENT, selectbackground=ACCENT_DIM,
            state="disabled", height=12
        )
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.text.tag_configure("info",    foreground="#9ca3b0")
        self.text.tag_configure("success", foreground=SUCCESS)
        self.text.tag_configure("warning", foreground=WARNING)
        self.text.tag_configure("error",   foreground=DANGER)

    def append(self, msg: str):
        tag = "info"
        if "✔" in msg or "sucesso" in msg.lower() or "extraído" in msg.lower():
            tag = "success"
        elif "!" in msg or "warning" in msg.lower() or "pausa" in msg.lower():
            tag = "warning"
        elif "erro" in msg.lower() or "crítico" in msg.lower() or "✗" in msg:
            tag = "error"

        ts = datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"[{ts}] {msg}\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# ──────────────────────────────────────────────────────────────
# Widget: Barra de progresso customizada
# ──────────────────────────────────────────────────────────────
class ProgressBar(tk.Canvas):
    def __init__(self, parent, height=6, **kw):
        super().__init__(parent, height=height, bg=BG_INPUT,
                         highlightthickness=0, **kw)
        self._pct = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct: float):
        self._pct = max(0.0, min(1.0, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        r = h // 2
        # trilha
        self.create_rectangle(0, 0, w, h, fill=BG_INPUT, outline="")
        # preenchimento
        fill_w = int(w * self._pct)
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, h, fill=ACCENT, outline="")


# ──────────────────────────────────────────────────────────────
# Aba 1: Extração de PDF
# ──────────────────────────────────────────────────────────────
class AbaExtracao(tk.Frame):
    def __init__(self, parent, log_panel: LogPanel):
        super().__init__(parent, bg=BG)
        self.log = log_panel
        self._rodando = False
        self.colunas_disponiveis = []   # colunas detectadas no PDF selecionado
        self._build()

    def _build(self):
        # ── Título
        tk.Label(self, text="Extrair dados do PDF",
                 font=("Georgia", 14, "bold"), fg=TEXT, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self, text="Lê o PDF do SISU e gera uma planilha .xlsx com todos os registros.",
                 font=FONT_LABEL, fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=24, pady=(0, 16))

        # ── Card de inputs
        card = tk.Frame(self, bg=BG_CARD, padx=20, pady=16)
        card.pack(fill="x", padx=24)

        self._linha_arquivo(card, "PDF de entrada:", "pdf_path", self._escolher_pdf, 0)
        self._linha_arquivo(card, "Planilha de saída:", "xlsx_out", self._escolher_xlsx_out, 1)
        self._linha_texto(card, "Filtrar colunas:", "colunas_desejadas", 2,
                           placeholder_hint="ex: NOME, ESCORE, Curso  (vazio = todas)")

        # Dispara o preview toda vez que o texto do filtro muda
        self.colunas_desejadas.trace_add("write", lambda *a: self._atualizar_preview())

        # ── Card de pré-visualização de colunas (NOVO)
        preview_card = tk.Frame(self, bg=BG_CARD, padx=20, pady=14)
        preview_card.pack(fill="x", padx=24, pady=(12, 0))

        top_row = tk.Frame(preview_card, bg=BG_CARD)
        top_row.pack(fill="x")
        tk.Label(top_row, text="🔎 PRÉ-VISUALIZAÇÃO DE COLUNAS", font=FONT_BADGE,
                 fg=TEXT_DIM, bg=BG_CARD).pack(side="left")
        self.lbl_colunas_status = tk.Label(
            top_row, text="Selecione um PDF para detectar as colunas",
            font=FONT_BADGE, fg=TEXT_DIM, bg=BG_CARD
        )
        self.lbl_colunas_status.pack(side="right")

        tk.Frame(preview_card, bg=BORDER, height=1).pack(fill="x", pady=(10, 10))

        self.lbl_preview_header = tk.Label(
            preview_card,
            text="Nenhum filtro definido — todas as colunas serão exportadas.",
            font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD, anchor="w", justify="left"
        )
        self.lbl_preview_header.pack(fill="x")

        self.preview_text = tk.Text(
            preview_card, bg=BG_INPUT, fg=TEXT, font=FONT_MONO,
            relief="flat", bd=0, wrap="word", height=3,
            state="disabled", cursor="arrow", padx=10, pady=8
        )
        self.preview_text.pack(fill="x", pady=(8, 0))
        self.preview_text.tag_configure("valid", foreground=SUCCESS)
        self.preview_text.tag_configure("invalid", foreground=DANGER)
        self.preview_text.tag_configure("sep", foreground=TEXT_DIM)
        self.preview_text.tag_configure("hint", foreground=TEXT_DIM, font=("Courier New", 9, "italic"))

        # ── Botão
        self.btn = self._botao_acao(self, "EXTRAIR PDF", self._iniciar)
        self.btn.pack(pady=16, padx=24, fill="x")

        # ── Progresso
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=24)
        self.lbl_prog = tk.Label(prog_frame, text="", font=FONT_MONO, fg=TEXT_DIM, bg=BG)
        self.lbl_prog.pack(anchor="w")
        self.bar = ProgressBar(prog_frame)
        self.bar.pack(fill="x", pady=(4, 0))

        # ── Estatísticas
        self.lbl_stats = tk.Label(self, text="", font=FONT_LABEL, fg=SUCCESS, bg=BG)
        self.lbl_stats.pack(anchor="w", padx=24, pady=(8, 0))

        # Estado inicial do preview
        self._atualizar_preview()

    def _linha_arquivo(self, parent, label, attr, cmd, row):
        tk.Label(parent, text=label, font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=18, anchor="w").grid(row=row, column=0, sticky="w", pady=6)

        var = tk.StringVar()
        setattr(self, attr, var)

        entry = tk.Entry(parent, textvariable=var, font=FONT_MONO,
                         bg=BG_INPUT, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", bd=6)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=6)

        tk.Button(parent, text="…", font=FONT_BTN, fg=TEXT, bg=BG_INPUT,
                  activebackground=ACCENT, activeforeground="white",
                  relief="flat", cursor="hand2", width=3, command=cmd
                  ).grid(row=row, column=2, pady=6)

        parent.columnconfigure(1, weight=1)

    def _linha_texto(self, parent, label, attr, row, placeholder="", placeholder_hint=""):
        tk.Label(parent, text=label, font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=18, anchor="w").grid(row=row, column=0, sticky="nw", pady=6)

        var = tk.StringVar(value=placeholder)
        setattr(self, attr, var)

        wrap = tk.Frame(parent, bg=BG_CARD)
        wrap.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=6)
        wrap.columnconfigure(0, weight=1)

        entry = tk.Entry(wrap, textvariable=var, font=FONT_MONO,
                         bg=BG_INPUT, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", bd=6)
        entry.grid(row=0, column=0, sticky="ew")

        if placeholder_hint:
            tk.Label(wrap, text=placeholder_hint, font=("Courier New", 8, "italic"),
                     fg=TEXT_DIM, bg=BG_CARD, anchor="w").grid(row=1, column=0, sticky="w", pady=(3, 0))

    def _botao_acao(self, parent, texto, cmd):
        return tk.Button(
            parent, text=texto, font=FONT_BTN, fg="white", bg=ACCENT,
            activebackground=ACCENT_DIM, activeforeground="white",
            relief="flat", cursor="hand2", pady=10, command=cmd
        )

    def _escolher_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.pdf_path.set(p)
            if not self.xlsx_out.get():
                self.xlsx_out.set(str(Path(p).with_suffix(".xlsx")))
            self._detectar_colunas_async(p)

    def _escolher_xlsx_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                          filetypes=[("Excel", "*.xlsx")])
        if p:
            self.xlsx_out.set(p)

    # ──────────────────────────────────────────────────────
    # Detecção e pré-visualização das colunas (NOVO)
    # ──────────────────────────────────────────────────────
    def _detectar_colunas_async(self, pdf_path):
        self.colunas_disponiveis = []
        self.lbl_colunas_status.configure(text="🔄  detectando colunas…", fg=TEXT_DIM)
        threading.Thread(target=self._detectar_colunas_thread, args=(pdf_path,), daemon=True).start()

    def _detectar_colunas_thread(self, pdf_path):
        colunas = detectar_colunas_pdf(pdf_path)
        self.after(0, lambda: self._colunas_detectadas(colunas))

    def _colunas_detectadas(self, colunas):
        self.colunas_disponiveis = colunas
        if colunas:
            self.lbl_colunas_status.configure(
                text=f"📋 {len(colunas)} colunas detectadas no PDF", fg=SUCCESS
            )
        else:
            self.lbl_colunas_status.configure(
                text="⚠ não foi possível detectar as colunas automaticamente", fg=WARNING
            )
        self._atualizar_preview()

    def _atualizar_preview(self):
        texto = self.colunas_desejadas.get().strip()
        disponiveis = self.colunas_disponiveis or []
        disp_upper = {c.upper(): c for c in disponiveis if c}

        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")

        if not texto:
            # Sem filtro: todas as colunas do PDF serão exportadas
            if disponiveis:
                self.lbl_preview_header.configure(
                    text=f"✓  Todas as {len(disponiveis)} colunas serão exportadas:",
                    fg=SUCCESS
                )
                for i, col in enumerate(disponiveis):
                    if i > 0:
                        self.preview_text.insert("end", "   ·   ", "sep")
                    self.preview_text.insert("end", col, "valid")
            else:
                self.lbl_preview_header.configure(
                    text="Nenhum filtro definido — todas as colunas serão exportadas.",
                    fg=TEXT_DIM
                )
                self.preview_text.insert(
                    "end", "Selecione um PDF para ver a lista completa de colunas disponíveis.", "hint"
                )
        else:
            itens = [c.strip() for c in texto.split(",") if c.strip()]
            validos, invalidos = [], []
            for item in itens:
                if item.upper() in disp_upper:
                    validos.append(disp_upper[item.upper()])
                else:
                    invalidos.append(item)

            total_disp = len(disponiveis) if disponiveis else None

            if invalidos:
                cor_header = DANGER if not validos else WARNING
                icone = "✗" if not validos else "⚠"
            else:
                cor_header = SUCCESS
                icone = "✓"

            if total_disp:
                texto_header = f"{icone}  {len(validos)} de {total_disp} colunas selecionadas"
            else:
                texto_header = f"{icone}  {len(validos)} coluna(s) reconhecida(s) (selecione um PDF para validar)"

            self.lbl_preview_header.configure(text=texto_header, fg=cor_header)

            primeiro = True
            for col in validos:
                if not primeiro:
                    self.preview_text.insert("end", "   ·   ", "sep")
                self.preview_text.insert("end", f"✓ {col}", "valid")
                primeiro = False

            if invalidos:
                if not primeiro:
                    self.preview_text.insert("end", "\n", "sep")
                primeiro_inv = True
                for col in invalidos:
                    if not primeiro_inv:
                        self.preview_text.insert("end", "   ·   ", "sep")
                    self.preview_text.insert("end", f"✗ {col} (não encontrada)", "invalid")
                    primeiro_inv = False

        self.preview_text.configure(state="disabled")

    def _iniciar(self):
        if self._rodando:
            return
        pdf = self.pdf_path.get().strip()
        out = self.xlsx_out.get().strip()
        colunas = self.colunas_desejadas.get().strip()

        if not pdf:
            messagebox.showerror("Erro", "Selecione o arquivo PDF.")
            return
        if not Path(pdf).exists():
            messagebox.showerror("Erro", "Arquivo PDF não encontrado.")
            return
        if not out:
            messagebox.showerror("Erro", "Defina o caminho de saída.")
            return

        self._rodando = True
        self.btn.configure(text="EXTRAINDO…", state="disabled", bg=ACCENT_DIM)
        self.lbl_stats.configure(text="")
        self.bar.set(0)

        threading.Thread(
            target=extrair_pdf,
            args=(pdf, out, colunas, self._cb_progresso, self._cb_fim),
            daemon=True
        ).start()

    def _cb_progresso(self, atual, total, texto):
        pct = atual / total if total else 0
        self.bar.set(pct)
        self.lbl_prog.configure(text=f"{texto}  ({atual}/{total})  {pct*100:.0f}%")
        self.log.append(f"Extraindo: {texto}")

    def _cb_fim(self, ok, msg):
        self._rodando = False
        self.btn.configure(text="EXTRAIR PDF", state="normal", bg=ACCENT)
        self.bar.set(1.0 if ok else 0)
        cor = SUCCESS if ok else DANGER
        self.lbl_stats.configure(text=("✔  " if ok else "✗  ") + msg, fg=cor)
        self.log.append(msg)
        if ok:
            messagebox.showinfo("Concluído", msg)
        else:
            messagebox.showerror("Erro", msg)


# ──────────────────────────────────────────────────────────────
# Aba 2: Busca de E-mails
# ──────────────────────────────────────────────────────────────
class AbaBusca(tk.Frame):
    def __init__(self, parent, log_panel: LogPanel):
        super().__init__(parent, bg=BG)
        self.log = log_panel
        self._rodando = False
        self._login_event = threading.Event()
        self.colunas_disponiveis = []   # colunas detectadas na planilha de entrada
        self._build()

    def _build(self):
        tk.Label(self, text="Buscar e-mails no Google Contacts",
                 font=("Georgia", 14, "bold"), fg=TEXT, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self,
                 text="Pesquisa cada nome da planilha no diretório do Google Contacts e coleta o e-mail.",
                 font=FONT_LABEL, fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=24, pady=(0, 16))

        # ── Card de inputs
        card = tk.Frame(self, bg=BG_CARD, padx=20, pady=16)
        card.pack(fill="x", padx=24)

        self._linha_arquivo(card, "Planilha de entrada:", "xlsx_in", self._escolher_xlsx_in, 0)
        self._linha_arquivo(card, "Planilha de saída:", "xlsx_out", self._escolher_xlsx_out, 1)

        # ── Estilo do combobox (tema escuro)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TCombobox",
                         fieldbackground=BG_INPUT, background=BG_INPUT,
                         foreground=TEXT, arrowcolor=TEXT_DIM,
                         bordercolor=BG_INPUT, lightcolor=BG_INPUT, darkcolor=BG_INPUT,
                         relief="flat", padding=6)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", BG_INPUT), ("!disabled", BG_INPUT)],
                  foreground=[("readonly", TEXT), ("!disabled", TEXT)],
                  selectbackground=[("!disabled", BG_INPUT)],
                  selectforeground=[("!disabled", TEXT)])

        # ── Coluna do nome a ser buscado (NOVO)
        tk.Label(card, text="Coluna do nome:", font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=20, anchor="w").grid(row=2, column=0, sticky="w", pady=6)

        combo_wrap = tk.Frame(card, bg=BG_CARD)
        combo_wrap.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=6)
        combo_wrap.columnconfigure(0, weight=1)

        self.coluna_nome = tk.StringVar(value="NOME")
        self.combo_coluna_nome = ttk.Combobox(
            combo_wrap, textvariable=self.coluna_nome, values=[],
            font=FONT_MONO, style="Dark.TCombobox"
        )
        self.combo_coluna_nome.grid(row=0, column=0, sticky="ew")

        self.lbl_colunas_email_status = tk.Label(
            combo_wrap, text="Selecione a planilha de entrada para listar as colunas",
            font=("Courier New", 8, "italic"), fg=TEXT_DIM, bg=BG_CARD, anchor="w"
        )
        self.lbl_colunas_email_status.grid(row=1, column=0, sticky="w", pady=(3, 0))

        # ── Navegador para scraping
        tk.Label(card, text="Navegador:", font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=20, anchor="w").grid(row=3, column=0, sticky="w", pady=6)

        nav_wrap = tk.Frame(card, bg=BG_CARD)
        nav_wrap.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=6)
        nav_wrap.columnconfigure(0, weight=1)

        self.navegador_var = tk.StringVar(value=obter_navegador_padrao())
        self.combo_navegador = ttk.Combobox(
            nav_wrap, textvariable=self.navegador_var, values=NAVEGADORES,
            font=FONT_MONO, style="Dark.TCombobox", state="readonly"
        )
        self.combo_navegador.grid(row=0, column=0, sticky="ew")
        self.combo_navegador.bind("<<ComboboxSelected>>", lambda e: self._on_navegador_changed())

        self.lbl_navegador_status = tk.Label(
            nav_wrap, text="",
            font=("Courier New", 8, "italic"), fg=TEXT_DIM, bg=BG_CARD, anchor="w"
        )
        self.lbl_navegador_status.grid(row=1, column=0, sticky="w", pady=(3, 0))

        # ── Perfil / Sessão
        self.lbl_sessao_titulo = tk.Label(card, text="Sessão salva:", font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=20, anchor="w")
        self.lbl_sessao_titulo.grid(row=4, column=0, sticky="w", pady=(10, 4))

        sessao_wrap = tk.Frame(card, bg=BG_CARD)
        sessao_wrap.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(10, 4))
        sessao_wrap.columnconfigure(0, weight=1)

        self.lbl_sessao_status = tk.Label(
            sessao_wrap, text="", font=FONT_MONO, fg=TEXT_DIM, bg=BG_CARD, anchor="w"
        )
        self.lbl_sessao_status.grid(row=0, column=0, sticky="w")

        self.btn_limpar_sessao = tk.Button(
            sessao_wrap, text="Limpar Sessão / Trocar Conta", font=FONT_BADGE,
            fg=TEXT_DIM, bg=BG_INPUT, activebackground=DANGER, activeforeground="white",
            relief="flat", cursor="hand2", padx=8, pady=3,
            command=self._limpar_sessao
        )
        self.btn_limpar_sessao.grid(row=0, column=1, sticky="e")

        # ── Botões
        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=24, pady=(16, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        self.btn_start = tk.Button(
            btns, text="INICIAR BUSCA", font=FONT_BTN, fg="white", bg=ACCENT,
            activebackground=ACCENT_DIM, relief="flat", cursor="hand2",
            pady=10, command=self._iniciar
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_stop = tk.Button(
            btns, text="PARAR", font=FONT_BTN, fg="white", bg=DANGER,
            activebackground="#c0392b", relief="flat", cursor="hand2",
            pady=10, state="disabled", command=self._parar
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # ── Banner de login (oculto inicialmente)
        self.banner_login = tk.Frame(self, bg="#1a2a1a", padx=16, pady=12)
        tk.Label(self.banner_login,
                 text="🌐  O navegador foi aberto. Faça login no Google Contacts e clique abaixo.",
                 font=FONT_LABEL, fg=SUCCESS, bg="#1a2a1a", wraplength=520, justify="left"
                 ).pack(side="left", expand=True, fill="x")
        tk.Button(
            self.banner_login, text="JÁ FIZ LOGIN →", font=FONT_BTN,
            fg="white", bg=SUCCESS, activebackground="#2eaf72",
            relief="flat", cursor="hand2", padx=12, pady=6,
            command=self._confirmar_login
        ).pack(side="right")

        # ── Progresso
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=24, pady=(12, 0))

        self.lbl_nome = tk.Label(prog_frame, text="", font=FONT_MONO, fg=TEXT, bg=BG,
                                  anchor="w")
        self.lbl_nome.pack(fill="x")
        self.lbl_eta = tk.Label(prog_frame, text="", font=FONT_MONO, fg=TEXT_DIM, bg=BG,
                                 anchor="w")
        self.lbl_eta.pack(fill="x")

        self.bar = ProgressBar(prog_frame, height=8)
        self.bar.pack(fill="x", pady=(6, 0))

        # ── Contadores
        cont_frame = tk.Frame(self, bg=BG)
        cont_frame.pack(fill="x", padx=24, pady=12)
        self.lbl_encontrados = self._badge(cont_frame, "0", "E-mails",    SUCCESS)
        self.lbl_sem_email   = self._badge(cont_frame, "0", "Sem e-mail", WARNING)
        self.lbl_erros       = self._badge(cont_frame, "0", "Erros",      DANGER)

        # ── Status final
        self.lbl_fim = tk.Label(self, text="", font=FONT_LABEL, fg=SUCCESS, bg=BG)
        self.lbl_fim.pack(anchor="w", padx=24)

        # Inicializa detecção do navegador e status da sessão
        self._on_navegador_changed()

    def _badge(self, parent, valor, rotulo, cor):
        f = tk.Frame(parent, bg=BG_CARD, padx=14, pady=8)
        f.pack(side="left", padx=(0, 8))
        lbl_val = tk.Label(f, text=valor, font=("Georgia", 18, "bold"), fg=cor, bg=BG_CARD)
        lbl_val.pack()
        tk.Label(f, text=rotulo, font=FONT_BADGE, fg=TEXT_DIM, bg=BG_CARD).pack()
        return lbl_val

    def _linha_arquivo(self, parent, label, attr, cmd, row):
        tk.Label(parent, text=label, font=FONT_LABEL, fg=TEXT_DIM, bg=BG_CARD,
                 width=20, anchor="w").grid(row=row, column=0, sticky="w", pady=6)
        var = tk.StringVar()
        setattr(self, attr, var)
        tk.Entry(parent, textvariable=var, font=FONT_MONO,
                 bg=BG_INPUT, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", bd=6).grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=6)
        tk.Button(parent, text="…", font=FONT_BTN, fg=TEXT, bg=BG_INPUT,
                  activebackground=ACCENT, activeforeground="white",
                  relief="flat", cursor="hand2", width=3,
                  command=cmd).grid(row=row, column=2, pady=6)
        parent.columnconfigure(1, weight=1)

    def _escolher_xlsx_in(self):
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if p:
            self.xlsx_in.set(p)
            if not self.xlsx_out.get():
                stem = Path(p).stem
                self.xlsx_out.set(str(Path(p).parent / f"{stem}_com_email.xlsx"))
            self._detectar_colunas_email_async(p)

    # ──────────────────────────────────────────────────────
    # Detecção das colunas da planilha para escolher a coluna do nome (NOVO)
    # ──────────────────────────────────────────────────────
    def _detectar_colunas_email_async(self, xlsx_path):
        self.colunas_disponiveis = []
        self.lbl_colunas_email_status.configure(text="🔄  detectando colunas…", fg=TEXT_DIM)
        threading.Thread(target=self._detectar_colunas_email_thread, args=(xlsx_path,), daemon=True).start()

    def _detectar_colunas_email_thread(self, xlsx_path):
        colunas = []
        try:
            colunas = pd.read_excel(xlsx_path, nrows=0).columns.tolist()
        except Exception:
            colunas = []
        self.after(0, lambda: self._colunas_email_detectadas(colunas))

    def _colunas_email_detectadas(self, colunas):
        self.colunas_disponiveis = colunas
        self.combo_coluna_nome["values"] = colunas

        if colunas:
            if "NOME" in colunas:
                self.coluna_nome.set("NOME")
            elif self.coluna_nome.get() not in colunas:
                self.coluna_nome.set(colunas[0])
            self.lbl_colunas_email_status.configure(
                text=f"📋 {len(colunas)} colunas encontradas — coluna do nome selecionada automaticamente",
                fg=SUCCESS
            )
        else:
            self.lbl_colunas_email_status.configure(
                text="⚠ não foi possível ler as colunas da planilha", fg=WARNING
            )

    def _escolher_xlsx_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                          filetypes=[("Excel", "*.xlsx")])
        if p:
            self.xlsx_out.set(p)

    def _iniciar(self):
        if self._rodando:
            return
        xlsx = self.xlsx_in.get().strip()
        out  = self.xlsx_out.get().strip()
        coluna = self.coluna_nome.get().strip()

        if not xlsx or not Path(xlsx).exists():
            messagebox.showerror("Erro", "Selecione uma planilha de entrada válida.")
            return
        if not out:
            messagebox.showerror("Erro", "Defina o caminho de saída.")
            return
        if not coluna:
            messagebox.showerror("Erro", "Selecione a coluna que contém o nome a ser buscado.")
            return
        if self.colunas_disponiveis and coluna not in self.colunas_disponiveis:
            messagebox.showerror(
                "Erro",
                f"A coluna '{coluna}' não existe na planilha selecionada.\n"
                f"Colunas disponíveis: {', '.join(self.colunas_disponiveis)}"
            )
            return

        _stop_flag.clear()
        self._login_event.clear()
        self._rodando = True
        self.btn_start.configure(state="disabled", bg=ACCENT_DIM, text="BUSCANDO…")
        self.btn_stop.configure(state="normal")
        self.lbl_fim.configure(text="")
        self.bar.set(0)

        nav = self.navegador_var.get().strip() or "Google Chrome"
        ok_nav, _ = detectar_navegador(nav)
        if not ok_nav:
            messagebox.showerror(
                "Erro",
                f"O navegador '{nav}' não foi encontrado no sistema.\n\n"
                f"Por favor, instale-o ou selecione outro navegador na lista."
            )
            return

        threading.Thread(
            target=buscar_emails,
            args=(xlsx, out, coluna, self._cb_progresso, self._cb_status, self._cb_fim, self._login_event, nav),
            daemon=True
        ).start()

    def _parar(self):
        _stop_flag.set()
        self._login_event.set()  # desbloqueia a thread se estiver aguardando login
        self.log.append("Interrupção solicitada pelo usuário...")
        self.btn_stop.configure(state="disabled")

    def _confirmar_login(self):
        self._login_event.set()
        self.banner_login.pack_forget()
        self.log.append("Login confirmado. Iniciando buscas...")

    def _cb_status(self, status: str):
        if status == "aguardando_login":
            self.banner_login.pack(fill="x", padx=24, pady=(12, 0))
            self.log.append("Aguardando login no Google Contacts...")
        elif status == "logado":
            self.banner_login.pack_forget()
            self._atualizar_status_sessao()

    def _cb_progresso(self, atual, total, nome, eta, encontrados, sem_email, erros):
        pct = atual / total if total else 0
        self.bar.set(pct)
        self.lbl_nome.configure(text=f"[{atual}/{total}]  {nome}")
        self.lbl_eta.configure(text=f"ETA: {eta}  ·  {pct*100:.1f}%")
        self.lbl_encontrados.configure(text=str(encontrados))
        self.lbl_sem_email.configure(text=str(sem_email))
        self.lbl_erros.configure(text=str(erros))

    def _cb_fim(self, ok: bool, msg: str):
        self._rodando = False
        self.banner_login.pack_forget()
        self.btn_start.configure(state="normal", bg=ACCENT, text="INICIAR BUSCA")
        self.btn_stop.configure(state="disabled")
        self.bar.set(1.0 if ok else 0)
        cor = SUCCESS if ok else DANGER
        self.lbl_fim.configure(text=("✔  " if ok else "✗  ") + msg, fg=cor)
        self.log.append(msg)
        self._atualizar_status_sessao()
        if ok:
            messagebox.showinfo("Concluído", msg)
        else:
            messagebox.showerror("Erro", msg)

    def _on_navegador_changed(self):
        nav = self.navegador_var.get().strip()
        instalado, detalhe = detectar_navegador(nav)
        if instalado:
            self.lbl_navegador_status.configure(
                text=f"✔ Instalado no sistema ({detalhe})", fg=SUCCESS
            )
        else:
            self.lbl_navegador_status.configure(
                text="⚠ Não encontrado no sistema (instale-o antes de usar)", fg=WARNING
            )
        self._atualizar_status_sessao()

    def _atualizar_status_sessao(self):
        nav = self.navegador_var.get().strip() if hasattr(self, "navegador_var") else "Google Chrome"
        if hasattr(self, "lbl_sessao_titulo"):
            self.lbl_sessao_titulo.configure(text=f"Sessão ({nav}):")
        if sessao_existe(nav):
            self.lbl_sessao_status.configure(
                text="● Sessão salva no perfil (login automático)", fg=SUCCESS
            )
            self.btn_limpar_sessao.configure(state="normal")
        else:
            self.lbl_sessao_status.configure(
                text="○ Nenhuma sessão salva (será solicitado login)", fg=TEXT_DIM
            )
            self.btn_limpar_sessao.configure(state="disabled")

    def _limpar_sessao(self):
        if self._rodando:
            messagebox.showwarning("Aviso", "Não é possível limpar a sessão enquanto a busca estiver em execução.")
            return
        nav = self.navegador_var.get().strip() or "Google Chrome"
        resp = messagebox.askyesno(
            f"Limpar Sessão do {nav}",
            f"Deseja realmente excluir os dados salvos de login do {nav}?\n\n"
            f"Isso desconectará a conta salva e exigirá novo login na próxima busca."
        )
        if resp:
            limpar_sessao(nav)
            self._atualizar_status_sessao()
            self.log.append(f"Dados de perfil e sessão do {nav} foram excluídos com sucesso.")


# ──────────────────────────────────────────────────────────────
# Janela principal
# ──────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SISU 2026 — Extração & E-mails")
        self.configure(bg=BG)
        self.geometry("720x820")
        self.minsize(640, 700)
        self._setup_logging()
        self._build()

    def _setup_logging(self):
        handler = QueueHandler()
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        self.after(100, self._poll_log)

    def _poll_log(self):
        try:
            while True:
                msg = log_queue.get_nowait()
                self.log_panel.append(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _build(self):
        # ── Cabeçalho
        header = tk.Frame(self, bg=BG, pady=0)
        header.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(header, text="Tativis SISU - 2026", font=FONT_TITLE,
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(header, text="  /  Extração & E-mails",
                 font=("Georgia", 14), fg=TEXT_DIM, bg=BG).pack(side="left", pady=(4, 0))

        # Linha divisória
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(12, 0))

        # ── Notebook (abas)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook",
                         background=BG, borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("Dark.TNotebook.Tab",
                         background=BG_CARD, foreground=TEXT_DIM,
                         font=FONT_BTN, padding=[20, 8],
                         borderwidth=0)
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        # Painel de log (compartilhado entre abas)
        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill="x", padx=24, pady=(0, 12))

        aba1 = AbaExtracao(nb, self.log_panel)
        aba2 = AbaBusca(nb, self.log_panel)

        nb.add(aba1, text="  📄  Extrair PDF  ")
        nb.add(aba2, text="  📧  Buscar E-mails  ")

        # Rodapé
        tk.Label(self, text="Use as abas em sequência: primeiro extraia o PDF, depois busque os e-mails.",
                 font=FONT_BADGE, fg=TEXT_DIM, bg=BG).pack(pady=(0, 8))


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()