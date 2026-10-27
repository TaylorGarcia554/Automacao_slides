"""Janela principal (Tkinter/ttk).

Layout em grade: a coluna dos campos tem peso 1, então os campos, a barra de
progresso e o registro crescem junto com a janela na horizontal.
O processamento roda numa thread separada para a janela não travar.
"""

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import APP_NAME, __version__
from . import processor
from .config import Settings, log_path

log = logging.getLogger("automacao_slides")

PAD = 10


def open_in_explorer(path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 - abre a pasta no Explorer
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class PathField:
    """Uma linha "rótulo | campo | botões" dentro de uma grade."""

    def __init__(self, parent, row, label, variable, browse, extra_buttons=()):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, PAD), pady=4)
        self.entry = ttk.Entry(parent, textvariable=variable)
        self.entry.grid(row=row, column=1, sticky="ew", pady=4)
        buttons = ttk.Frame(parent)
        buttons.grid(row=row, column=2, sticky="e", padx=(PAD, 0), pady=4)
        self.widgets = [self.entry]
        for text, command in (("Selecionar…", browse), *extra_buttons):
            btn = ttk.Button(buttons, text=text, command=command)
            btn.pack(side="left", padx=(0, 4))
            self.widgets.append(btn)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = Settings.load()
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.cancel_flag = threading.Event()
        self.worker = None

        self.source_var = tk.StringVar(value=self.settings.source_folder)
        self.image_var = tk.StringVar(value=self.settings.image_path)
        self.output_var = tk.StringVar(value=self.settings.output_folder)
        self.subfolders_var = tk.BooleanVar(value=self.settings.include_subfolders)
        self.replace_var = tk.BooleanVar(value=self.settings.replace_previous_background)
        self.open_when_done_var = tk.BooleanVar(value=self.settings.open_output_when_done)
        self.found_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto.")

        self._setup_window()
        self._setup_style()
        self._build()

        self.source_var.trace_add("write", lambda *_: self.refresh_count())
        self.subfolders_var.trace_add("write", lambda *_: self.refresh_count())
        self.output_var.trace_add("write", lambda *_: self.refresh_count())
        self.refresh_count()
        self.root.after(100, self._poll_events)

    # ------------------------------------------------------------------ setup
    def _setup_window(self):
        self.root.title(f"{APP_NAME} {__version__}")
        self.root.minsize(640, 460)
        self.root.geometry(self.settings.window_geometry or "860x600")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        style = ttk.Style(self.root)
        for theme in ("vista", "winnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        base = ("Segoe UI", 10) if sys.platform.startswith("win") else ("TkDefaultFont", 10)
        self.root.option_add("*Font", base)
        style.configure("Title.TLabel", font=(base[0], 16, "bold"))
        style.configure("Subtitle.TLabel", foreground="#5f6368")
        style.configure("Status.TLabel", foreground="#5f6368")
        style.configure("Accent.TButton", font=(base[0], 10, "bold"), padding=(14, 6))

    def _build(self):
        main = ttk.Frame(self.root, padding=PAD * 1.5)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)  # o registro ocupa o espaço que sobrar

        # Cabeçalho
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, PAD))
        ttk.Label(header, text="Processador de Slides", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, style="Subtitle.TLabel",
                  text="Aplica uma imagem de fundo em todos os slides das apresentações "
                       "de uma pasta e salva as cópias na pasta de saída."
                  ).pack(anchor="w", fill="x")

        # Configuração
        cfg = ttk.LabelFrame(main, text=" Configuração ", padding=PAD)
        cfg.grid(row=1, column=0, sticky="ew")
        cfg.columnconfigure(1, weight=1)

        self.f_source = PathField(cfg, 0, "Pasta dos slides:", self.source_var, self.browse_source,
                                  [("Abrir", lambda: open_in_explorer(self.source_var.get()))])
        ttk.Label(cfg, textvariable=self.found_var, style="Status.TLabel").grid(
            row=1, column=1, sticky="w", pady=(0, 4))
        self.f_image = PathField(cfg, 2, "Imagem de fundo:", self.image_var, self.browse_image)
        self.f_output = PathField(cfg, 3, "Pasta de saída:", self.output_var, self.browse_output,
                                  [("Abrir", lambda: open_in_explorer(self.output_var.get()))])

        opts = ttk.Frame(cfg)
        opts.grid(row=4, column=0, columnspan=3, sticky="w", pady=(PAD, 0))
        self.option_widgets = [
            ttk.Checkbutton(opts, text="Incluir subpastas", variable=self.subfolders_var),
            ttk.Checkbutton(opts, text="Substituir fundo aplicado anteriormente",
                            variable=self.replace_var),
            ttk.Checkbutton(opts, text="Abrir pasta de saída ao terminar",
                            variable=self.open_when_done_var),
        ]
        for cb in self.option_widgets:
            cb.pack(side="left", padx=(0, PAD * 2))

        # Ações + progresso
        actions = ttk.Frame(main)
        actions.grid(row=2, column=0, sticky="ew", pady=PAD)
        actions.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, PAD))
        self.btn_cancel = ttk.Button(actions, text="Cancelar", command=self.cancel, state="disabled")
        self.btn_cancel.grid(row=0, column=1, padx=(0, 6))
        self.btn_start = ttk.Button(actions, text="Iniciar processamento",
                                    style="Accent.TButton", command=self.start)
        self.btn_start.grid(row=0, column=2)

        # Registro
        log_frame = ttk.LabelFrame(main, text=" Registro ", padding=(PAD // 2))
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ScrolledText(log_frame, height=10, wrap="word", state="disabled",
                                    relief="flat", borderwidth=0, font=("Consolas", 9))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.tag_configure("ok", foreground="#1e7e34")
        self.log_box.tag_configure("error", foreground="#c62828")
        self.log_box.tag_configure("info", foreground="#37474f")

        # Barra de status
        status = ttk.Frame(main)
        status.grid(row=4, column=0, sticky="ew", pady=(PAD // 2, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Button(status, text="Limpar registro", command=self.clear_log).grid(row=0, column=1)

        self.input_widgets = (self.f_source.widgets + self.f_image.widgets
                              + self.f_output.widgets + self.option_widgets)
        self.root.bind("<Return>", lambda _e: self.start())

    # ------------------------------------------------------------- seletores
    def browse_source(self):
        folder = filedialog.askdirectory(title="Pasta com os arquivos .pptx",
                                         initialdir=self.source_var.get() or None)
        if folder:
            self.source_var.set(os.path.normpath(folder))

    def browse_image(self):
        current = self.image_var.get()
        exts = " ".join(f"*{e}" for e in processor.IMAGE_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="Imagem de fundo",
            initialdir=os.path.dirname(current) if current else None,
            filetypes=[("Imagens", exts), ("Todos os arquivos", "*.*")])
        if path:
            self.image_var.set(os.path.normpath(path))

    def browse_output(self):
        folder = filedialog.askdirectory(title="Pasta de saída",
                                         initialdir=self.output_var.get() or None)
        if folder:
            self.output_var.set(os.path.normpath(folder))

    # ------------------------------------------------------------ utilitários
    def refresh_count(self):
        folder = self.source_var.get().strip()
        if not folder:
            self.found_var.set("Nenhuma pasta selecionada.")
        elif not os.path.isdir(folder):
            self.found_var.set("Pasta não encontrada ou indisponível.")
        else:
            n = len(processor.find_presentations(folder, self.subfolders_var.get(),
                                                 exclude_folder=self.output_var.get().strip() or None))
            self.found_var.set(f"{n} arquivo(s) .pptx encontrado(s).")

    def write_log(self, text, tag="info"):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def set_running(self, running: bool):
        state = "disabled" if running else "normal"
        for w in self.input_widgets:
            w.configure(state=state)
        self.btn_start.configure(state=state)
        self.btn_cancel.configure(state="normal" if running else "disabled")

    def save_settings(self):
        s = self.settings
        s.source_folder = self.source_var.get().strip()
        s.image_path = self.image_var.get().strip()
        s.output_folder = self.output_var.get().strip()
        s.include_subfolders = self.subfolders_var.get()
        s.replace_previous_background = self.replace_var.get()
        s.open_output_when_done = self.open_when_done_var.get()
        s.window_geometry = self.root.geometry()
        try:
            s.save()
        except OSError:
            log.exception("Não foi possível salvar as configurações")

    # ----------------------------------------------------------- processamento
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        job = processor.Job(
            source_folder=self.source_var.get().strip(),
            image_path=self.image_var.get().strip(),
            output_folder=self.output_var.get().strip(),
            include_subfolders=self.subfolders_var.get(),
            replace_previous_background=self.replace_var.get(),
        )
        errors = processor.validate(job)
        if errors:
            messagebox.showerror("Verifique os campos", "\n".join(f"• {e}" for e in errors))
            return

        files = processor.find_presentations(job.source_folder, job.include_subfolders,
                                             exclude_folder=job.output_folder)
        if not files:
            messagebox.showinfo(APP_NAME, "Nenhum arquivo .pptx encontrado na pasta selecionada.")
            return

        existing = [f for f in files if os.path.exists(
            os.path.join(job.output_folder, os.path.relpath(f, job.source_folder)))]
        if existing and not messagebox.askyesno(
                "Arquivos existentes",
                f"{len(existing)} arquivo(s) já existem na pasta de saída e serão substituídos.\n\n"
                "Deseja continuar?"):
            return

        self.save_settings()
        self.cancel_flag.clear()
        self.progress.configure(maximum=len(files), value=0)
        self.set_running(True)
        self.status_var.set("Processando…")
        self.write_log(f"Iniciando: {len(files)} arquivo(s) de {job.source_folder}")
        log.info("Início: %s arquivo(s) | origem=%s | saída=%s | imagem=%s",
                 len(files), job.source_folder, job.output_folder, job.image_path)

        def work():
            try:
                result = processor.run(
                    job,
                    on_progress=lambda i, n, name, err: self.events.put(("progress", i, n, name, err)),
                    should_cancel=self.cancel_flag.is_set,
                )
                self.events.put(("done", result, job))
            except Exception as exc:  # erro inesperado fora de um arquivo específico
                log.exception("Falha no processamento")
                self.events.put(("fatal", str(exc)))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def cancel(self):
        self.cancel_flag.set()
        self.status_var.set("Cancelando após o arquivo atual…")

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                getattr(self, f"_on_{event[0]}")(*event[1:])
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _on_progress(self, index, total, name, error):
        self.progress.configure(value=index)
        self.status_var.set(f"Processando {index} de {total}…")
        if error:
            self.write_log(f"✗ {name} — {error}", "error")
            log.error("Erro em %s: %s", name, error)
        else:
            self.write_log(f"✓ {name}", "ok")
            log.info("OK %s", name)

    def _on_done(self, result: processor.Result, job: processor.Job):
        self.set_running(False)
        summary = f"{len(result.processed)} processado(s), {len(result.failed)} com erro"
        if result.cancelled:
            summary += f", {result.total - len(result.processed) - len(result.failed)} não processado(s) (cancelado)"
        self.status_var.set(f"Concluído: {summary}.")
        self.write_log(f"Concluído: {summary}.")
        log.info("Fim: %s", summary)

        if result.failed:
            details = "\n".join(f"• {os.path.basename(p)}: {e}" for p, e in result.failed[:10])
            more = f"\n… e mais {len(result.failed) - 10}" if len(result.failed) > 10 else ""
            messagebox.showwarning(APP_NAME, f"{summary}.\n\nArquivos com erro:\n{details}{more}")
        else:
            messagebox.showinfo(APP_NAME, f"{summary}.")
        if self.open_when_done_var.get() and result.processed:
            open_in_explorer(job.output_folder)

    def _on_fatal(self, message):
        self.set_running(False)
        self.status_var.set("Erro inesperado.")
        self.write_log(f"Erro inesperado: {message}", "error")
        messagebox.showerror(APP_NAME, f"Erro inesperado:\n{message}\n\nDetalhes em: {log_path()}")

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, "Há um processamento em andamento. Deseja sair mesmo assim?"):
                return
            self.cancel_flag.set()
        self.save_settings()
        self.root.destroy()


def setup_logging():
    try:
        logging.basicConfig(
            filename=log_path(), level=logging.INFO, encoding="utf-8",
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)


def main():
    setup_logging()
    if sys.platform.startswith("win"):
        try:  # texto nítido em telas com escala (125%, 150%…)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()
