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
def extrair_pdf(pdf_path: str, output_path: str, callback_progresso, callback_fim):
    try:
        import pdfplumber
        log = logging.getLogger("extrator")

        all_rows = []
        header = None

        # Palavra que identifica a linha de cabeçalho da tabela.
        # O PDF do SISU/UFBA usa "MUNICÍPIO" como primeira coluna
        # (em vez de "CURSO", que era o esperado originalmente).
        HEADER_MARK = "MUNIC"

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
                        primeira_col = str(row[0] or "").strip().upper()
                        if HEADER_MARK in primeira_col:
                            header = row
                        else:
                            all_rows.append(row)

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


def buscar_emails(xlsx_path: str, output_path: str,
                  callback_progresso, callback_status,
                  callback_fim, evento_login_ok: threading.Event):
    log = logging.getLogger("buscador")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException, NoSuchElementException,
            StaleElementReferenceException, WebDriverException,
        )
        from webdriver_manager.chrome import ChromeDriverManager

        # Carrega dados (retoma progresso se arquivo de saída já existir)
        if Path(output_path).exists():
            df = pd.read_excel(output_path, dtype={"NOME": str})
            log.info(f"Retomando progresso de: {output_path}")
        else:
            df = pd.read_excel(xlsx_path, dtype={"NOME": str})
            df["Email"] = None
            df["Status_Busca"] = None

        pendentes = df[df["Status_Busca"].isna()].index.tolist()
        total_pendentes = len(pendentes)

        if not pendentes:
            callback_fim(True, "Todos os registros já foram processados.")
            return

        log.info(f"Pendentes: {total_pendentes} | Já feitos: {len(df) - total_pendentes}")

        # Inicia navegador
        opcoes = Options()
        opcoes.add_experimental_option("detach", True)
        opcoes.add_argument("--disable-notifications")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opcoes
        )

        driver.get("https://contacts.google.com/")
        callback_status("aguardando_login")
        evento_login_ok.wait()  # UI vai setar esse evento quando usuário clicar "Já fiz login"

        if _stop_flag.is_set():
            driver.quit()
            callback_fim(False, "Cancelado pelo usuário.")
            return

        driver.get("https://contacts.google.com/directory")
        time.sleep(1.5)

        encontrados = sem_email = erros = 0
        inicio = time.monotonic()

        for posicao, idx in enumerate(pendentes, start=1):
            if _stop_flag.is_set():
                break

            nome = str(df.at[idx, "NOME"]).strip()

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
        msg = f"{posicao} registros | {encontrados} e-mails | {m}m {s:02d}s"
        callback_fim(True, msg)

    except Exception as e:
        callback_fim(False, str(e))


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

    def _escolher_xlsx_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                          filetypes=[("Excel", "*.xlsx")])
        if p:
            self.xlsx_out.set(p)

    def _iniciar(self):
        if self._rodando:
            return
        pdf = self.pdf_path.get().strip()
        out = self.xlsx_out.get().strip()

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
            args=(pdf, out, self._cb_progresso, self._cb_fim),
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

        if not xlsx or not Path(xlsx).exists():
            messagebox.showerror("Erro", "Selecione uma planilha de entrada válida.")
            return
        if not out:
            messagebox.showerror("Erro", "Defina o caminho de saída.")
            return

        _stop_flag.clear()
        self._login_event.clear()
        self._rodando = True
        self.btn_start.configure(state="disabled", bg=ACCENT_DIM, text="BUSCANDO…")
        self.btn_stop.configure(state="normal")
        self.lbl_fim.configure(text="")
        self.bar.set(0)

        threading.Thread(
            target=buscar_emails,
            args=(xlsx, out, self._cb_progresso, self._cb_status, self._cb_fim, self._login_event),
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
        self.btn_start.configure(state="normal", bg=ACCENT, text="INICIAR BUSCA")
        self.btn_stop.configure(state="disabled")
        self.bar.set(1.0 if ok else 0)
        cor = SUCCESS if ok else DANGER
        self.lbl_fim.configure(text=("✔  " if ok else "✗  ") + msg, fg=cor)
        self.log.append(msg)
        if ok:
            messagebox.showinfo("Concluído", msg)
        else:
            messagebox.showerror("Erro", msg)


# ──────────────────────────────────────────────────────────────
# Janela principal
# ──────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SISU 2026 — Extração & E-mails")
        self.configure(bg=BG)
        self.geometry("720x780")
        self.minsize(640, 680)
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