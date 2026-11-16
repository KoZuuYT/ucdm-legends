"""Janela do instalador (tkinter, só biblioteca padrão).

Assistente em etapas: Boas-vindas > Instalação > Jogo > Resumo > Instalando > Concluído.
Também tem o modo de desinstalação. Toda tarefa demorada roda numa thread e fala
com a janela por uma fila (o Tk só pode ser tocado pela thread principal).
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from fractions import Fraction
from pathlib import Path
from tkinter import filedialog, messagebox

from installer import setup_core as sc
from network import release_tools as rt

# --- paleta / tipografia ------------------------------------------------------------------------
BG = "#262626"
PANEL = "#313131"
CARD = "#4a4a4a"
CARD_HI = "#5c5c5c"
LINE = "#161616"
FG = "#f4f4f4"
MUTED = "#b4b4b4"
ACCENT = "#6cc04a"
ACCENT_HI = "#86da63"
ACCENT_FG = "#10200a"
DANGER = "#e0574a"
DANGER_HI = "#ee6d61"
OK = "#6cc04a"
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"

STEPS = ["Boas-vindas", "Instalação", "Jogo", "Resumo", "Instalando", "Pronto"]
STAGES = {"download": ("Baixando o jogo", 0.00, 0.80), "verify": ("Conferindo integridade", 0.80, 0.84),
          "extract": ("Extraindo arquivos", 0.84, 0.90), "install": ("Copiando para a pasta", 0.90, 0.97),
          "finish": ("Criando atalhos", 0.97, 1.00)}


def art_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "art"


def enable_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


# --- widgets próprios (visual consistente em qualquer Windows) ---------------------------------
class Button(tk.Label):
    STYLES = {"primary": (ACCENT, ACCENT_HI, ACCENT_FG), "secondary": (CARD, CARD_HI, FG),
              "danger": (DANGER, DANGER_HI, "#ffffff"), "ghost": (PANEL, CARD, MUTED), "link": (CARD, CARD_HI, ACCENT)}

    def __init__(self, master, text, command, style="primary", px=None, **kw):
        self.bg, self.hi, self.fg = self.STYLES[style]
        px = px or (lambda v: v)
        super().__init__(master, text=text, bg=self.bg, fg=self.fg, cursor="hand2",
                         font=(FONT, 10, "bold"), padx=px(18), pady=px(8), **kw)
        self.command, self.enabled = command, True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self.hi))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg if self.enabled else LINE))
        self.bind("<ButtonRelease-1>", self._click)

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        self.config(bg=self.bg if on else LINE, fg=self.fg if on else MUTED, cursor="hand2" if on else "arrow")

    def set_text(self, text: str) -> None:
        self.config(text=text)

    def set_style(self, style: str) -> None:
        self.bg, self.hi, self.fg = self.STYLES[style]
        self.set_enabled(self.enabled)


class Toggle(tk.Frame):
    """Interruptor liga/desliga com título e descrição."""

    def __init__(self, master, title, desc, var: tk.BooleanVar, px, bg=CARD):
        super().__init__(master, bg=bg)
        self.var, self.px = var, px
        w, h = px(44), px(24)
        self.cv = tk.Canvas(self, width=w, height=h, bg=bg, highlightthickness=0, cursor="hand2")
        self.cv.pack(side="right", padx=(px(12), 0))
        txt = tk.Frame(self, bg=bg)
        txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=title, bg=bg, fg=FG, font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
        if desc:
            tk.Label(txt, text=desc, bg=bg, fg=MUTED, font=(FONT, 9), anchor="w", justify="left",
                     wraplength=px(400)).pack(fill="x")
        for wdg in (self, self.cv, txt, *txt.winfo_children()):
            wdg.bind("<Button-1>", self._flip)
        var.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _flip(self, _e=None):
        self.var.set(not self.var.get())

    def _draw(self):
        c, px = self.cv, self.px
        c.delete("all")
        w, h = px(44), px(24)
        on = self.var.get()
        col = ACCENT if on else LINE
        r = h // 2
        c.create_oval(0, 0, h, h, fill=col, outline=col)
        c.create_oval(w - h, 0, w, h, fill=col, outline=col)
        c.create_rectangle(r, 0, w - r, h, fill=col, outline=col)
        k = px(3)
        x = w - h + k if on else k
        c.create_oval(x, k, x + h - 2 * k, h - k, fill="#ffffff" if on else MUTED, outline="")


class Segmented(tk.Frame):
    """Grupo de opções exclusivas (tipo abas)."""

    def __init__(self, master, options: list[tuple[str, object]], var: tk.Variable, px, bg=CARD):
        super().__init__(master, bg=LINE, padx=1, pady=1)
        self.var, self.items = var, []
        for label, value in options:
            b = tk.Label(self, text=label, font=(FONT, 9, "bold"), padx=px(10), pady=px(4), cursor="hand2")
            b.pack(side="left", padx=(0, 1))
            b.bind("<Button-1>", lambda e, v=value: var.set(v))
            self.items.append((b, value))
        var.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _draw(self):
        cur = self.var.get()
        for b, v in self.items:
            on = str(v) == str(cur)
            b.config(bg=ACCENT if on else CARD, fg=ACCENT_FG if on else FG)


class Slider(tk.Frame):
    """Barra de volume arrastável com porcentagem."""

    def __init__(self, master, var: tk.DoubleVar, px, bg=CARD):
        super().__init__(master, bg=bg)
        self.var, self.px = var, px
        self.w, self.h = px(190), px(22)
        self.cv = tk.Canvas(self, width=self.w, height=self.h, bg=bg, highlightthickness=0, cursor="hand2")
        self.cv.pack(side="left")
        self.lbl = tk.Label(self, bg=bg, fg=FG, font=(FONT, 9, "bold"), width=5, anchor="e")
        self.lbl.pack(side="left")
        for ev in ("<Button-1>", "<B1-Motion>"):
            self.cv.bind(ev, self._set)
        var.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _set(self, e):
        r = self.px(8)
        self.var.set(round(min(1.0, max(0.0, (e.x - r) / (self.w - 2 * r))), 2))

    def _draw(self):
        c, px = self.cv, self.px
        c.delete("all")
        r, mid = px(8), self.h // 2
        v = self.var.get()
        x = r + v * (self.w - 2 * r)
        c.create_line(r, mid, self.w - r, mid, fill=LINE, width=px(5), capstyle="round")
        c.create_line(r, mid, x, mid, fill=ACCENT, width=px(5), capstyle="round")
        c.create_oval(x - r, mid - r, x + r, mid + r, fill="#ffffff", outline=ACCENT, width=px(2))
        self.lbl.config(text=f"{int(round(v * 100))}%")


class ProgressBar(tk.Canvas):
    def __init__(self, master, px, height=14):
        super().__init__(master, height=px(height), bg=PANEL, highlightthickness=0)
        self.value, self.px, self._phase = 0.0, px, 0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, v: float) -> None:
        self.value = max(0.0, min(1.0, v))
        self._draw()

    def tick(self) -> None:
        self._phase = (self._phase + 2) % self.px(24)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, w, h, fill=CARD, outline="")
        fw = int(w * self.value)
        if fw > 0:
            self.create_rectangle(0, 0, fw, h, fill=ACCENT, outline="")
            step = self.px(24)
            for x in range(-step + self._phase, fw, step):   # listras animadas
                self.create_polygon(x, h, x + step // 2, h, min(x + step, fw), 0, min(x + step // 2, fw), 0,
                                    fill=ACCENT_HI, outline="")
            self.create_rectangle(fw, 0, w, h, fill=CARD, outline="")


def card(master, px, **kw):
    return tk.Frame(master, bg=CARD, padx=px(16), pady=px(12), **kw)


# --- aplicativo -----------------------------------------------------------------------------------
class InstallerApp:
    W, H, SIDE = 860, 640, 280

    def __init__(self, repo: str, mode: str = "install", target: Path | None = None) -> None:
        enable_dpi_awareness()
        self.repo, self.mode = repo, mode
        self.root = tk.Tk()
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.root.tk.call("tk", "scaling", 96 * self.scale / 72)
        self.root.title(f"{sc.APP_NAME} — {'Desinstalar' if mode == 'uninstall' else 'Instalador'}")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        w, h = self.px(self.W), self.px(self.H)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 30)}")
        self._set_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.q: queue.Queue = queue.Queue()
        self.release: sc.ReleaseInfo | None = None
        self.release_error: str | None = None
        self.existing = sc.find_existing()
        self.busy = False
        self.stage = ""
        self.fail_reason = ""
        self.cancel_flag = False
        self.finished_ok = False
        self.page_idx = 0
        self._dl = (0.0, 0, 0)  # (tempo, bytes) para velocidade

        st = sc.load_settings()
        d, a, u = st["display"], st["audio"], st["update"]
        default_target = target or (self.existing[0] if self.existing else sc.default_dir())
        self.v = {
            "dir": tk.StringVar(value=str(default_target)),
            "desktop": tk.BooleanVar(value=True), "start_menu": tk.BooleanVar(value=True),
            "register": tk.BooleanVar(value=sys.platform == "win32"), "launch": tk.BooleanVar(value=True),
            "fullscreen": tk.BooleanVar(value=bool(d.get("fullscreen"))),
            "fps_cap": tk.StringVar(value=str(d.get("fps_cap", 144) or 0)),
            "show_fps": tk.BooleanVar(value=bool(d.get("show_fps"))),
            "music": tk.DoubleVar(value=float(a.get("music_volume", 0.5))),
            "sfx": tk.DoubleVar(value=float(a.get("sfx_volume", 0.8))),
            "auto_update": tk.BooleanVar(value=bool(u.get("enabled", True))),
            "wipe": tk.BooleanVar(value=False),
        }
        self._build_shell()
        if mode == "uninstall":
            self.uninstall_target = Path(target) if target else (self.existing[0] if self.existing else None)
            self.pages = [self.page_uninstall, self.page_progress, self.page_done]
        else:
            self.pages = [self.page_welcome, self.page_options, self.page_game, self.page_summary,
                          self.page_progress, self.page_done]
            self._fetch_release()
        self.show(0)
        self.root.after(50, self._poll)

    # --- utilidades -------------------------------------------------------------------------
    def px(self, v: float) -> int:
        return int(round(v * self.scale))

    def _set_icon(self) -> None:
        try:
            if sys.platform == "win32" and (art_dir() / "icon.ico").exists():
                self.root.iconbitmap(default=str(art_dir() / "icon.ico"))
            else:
                self._icon = tk.PhotoImage(file=str(art_dir() / "icon.png"))
                self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass

    def _banner(self) -> tk.PhotoImage | None:
        try:
            src = art_dir() / ("banner@2x.png" if self.scale > 1.25 else "banner.png")
            img = tk.PhotoImage(file=str(src))
            base = 2 if "@2x" in src.name else 1
            f = Fraction(self.scale / base).limit_denominator(4)
            if f != 1:
                img = img.zoom(f.numerator, f.numerator).subsample(f.denominator, f.denominator)
            return img
        except tk.TclError:
            return None

    # --- estrutura fixa: lateral + cabeçalho + conteúdo + rodapé ------------------------------
    def _build_shell(self) -> None:
        px = self.px
        side = tk.Canvas(self.root, width=px(self.SIDE), height=px(self.H), bg="#3b2a1a", highlightthickness=0)
        side.pack(side="left", fill="y")
        self._banner_img = self._banner()
        if self._banner_img:
            side.create_image(0, 0, image=self._banner_img, anchor="nw")
        else:
            side.create_text(px(24), px(40), text="UCDM\nLEGENDS", fill=ACCENT, anchor="nw", font=(FONT, 28, "bold"))
        self.side = side
        self.side_steps = []
        y = px(self.H - 112)
        names = ["Confirmar", "Removendo", "Pronto"] if self.mode == "uninstall" else STEPS
        for i, name in enumerate(names):
            col, row = i % 2, i // 2
            x0, y0 = px(22) + col * px(128), y + row * px(30)
            dot = side.create_oval(x0, y0 + px(4), x0 + px(12), y0 + px(16), fill=LINE, outline="")
            txt = side.create_text(x0 + px(20), y0 + px(10), text=name, fill=MUTED, anchor="w", font=(FONT, 9))
            self.side_steps.append((dot, txt))

        right = tk.Frame(self.root, bg=PANEL)
        right.pack(side="left", fill="both", expand=True)
        head = tk.Frame(right, bg=PANEL, padx=px(32), pady=px(24))
        head.pack(fill="x")
        self.h_title = tk.Label(head, bg=PANEL, fg=FG, font=(FONT, 18, "bold"), anchor="w")
        self.h_title.pack(fill="x")
        self.h_sub = tk.Label(head, bg=PANEL, fg=MUTED, font=(FONT, 10), anchor="w", justify="left",
                              wraplength=px(self.W - self.SIDE - 64))
        self.h_sub.pack(fill="x", pady=(px(2), 0))
        tk.Frame(right, bg=LINE, height=1).pack(fill="x")

        foot = tk.Frame(right, bg=PANEL, padx=px(32), pady=px(16))
        foot.pack(side="bottom", fill="x")
        tk.Frame(right, bg=LINE, height=1).pack(side="bottom", fill="x")
        self.b_cancel = Button(foot, "Cancelar", self.on_close, "ghost", px)
        self.b_cancel.pack(side="left")
        self.b_next = Button(foot, "Próximo  ›", self.next, "primary", px)
        self.b_next.pack(side="right")
        self.b_back = Button(foot, "‹  Voltar", self.back, "secondary", px)
        self.b_back.pack(side="right", padx=(0, px(10)))
        self.foot_note = tk.Label(foot, bg=PANEL, fg=MUTED, font=(FONT, 9))
        self.foot_note.pack(side="left", padx=px(12))

        self.body = tk.Frame(right, bg=PANEL, padx=px(32), pady=px(20))
        self.body.pack(fill="both", expand=True)

    def show(self, idx: int) -> None:
        self.page_idx = idx
        for w in self.body.winfo_children():
            w.destroy()
        self.foot_note.config(text="")
        self.b_back.pack_forget()
        self.b_next.pack_forget()
        self.b_next.pack(side="right")
        if 0 < idx < len(self.pages) - 2 and self.mode == "install":
            self.b_back.pack(side="right", padx=(0, self.px(10)))
        if not self.b_cancel.winfo_ismapped():
            self.b_cancel.pack(side="left", before=self.foot_note)
        self.b_next.command = self.next
        self.b_next.set_text("Próximo  ›")
        self.b_next.set_style("primary")
        self.b_next.set_enabled(True)
        self.b_cancel.set_enabled(True)
        self.b_cancel.set_text("Cancelar")
        self.pages[idx]()
        for i, (dot, txt) in enumerate(self.side_steps):
            col = OK if i < idx else ACCENT if i == idx else LINE
            self.side.itemconfig(dot, fill=col)
            self.side.itemconfig(txt, fill=FG if i == idx else MUTED,
                                 font=(FONT, 9, "bold") if i == idx else (FONT, 9))

    def header(self, title: str, sub: str) -> None:
        self.h_title.config(text=title)
        self.h_sub.config(text=sub)

    def next(self) -> None:
        if self.page_idx < len(self.pages) - 1:
            self.show(self.page_idx + 1)

    def back(self) -> None:
        if self.page_idx > 0 and not self.busy:
            self.show(self.page_idx - 1)

    def on_close(self) -> None:
        if self.busy:
            if self.mode == "install" and self.stage == "download":
                if messagebox.askyesno(sc.APP_NAME, "Cancelar o download e sair do instalador?", parent=self.root):
                    self.cancel_flag = True
            return
        if self.page_idx < len(self.pages) - 1 and self.page_idx > 0 and self.mode == "install":
            if not messagebox.askyesno(sc.APP_NAME, "Sair do instalador? Nada foi instalado ainda.", parent=self.root):
                return
        self.root.destroy()

    # --- páginas: instalação ------------------------------------------------------------------
    def page_welcome(self) -> None:
        px = self.px
        self.header(f"Bem-vindo ao {sc.APP_NAME}",
                    "Este assistente baixa a versão mais recente do jogo direto do GitHub, confere a "
                    "integridade do arquivo e prepara tudo para você jogar.")
        if self.existing:
            c = card(self.body, px)
            c.pack(fill="x", pady=(0, px(12)))
            tk.Label(c, text="Já instalado neste computador", bg=CARD, fg=ACCENT, font=(FONT, 10, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(c, text=f"Versão {self.existing[1]}  •  {self.existing[0]}", bg=CARD, fg=MUTED,
                     font=(FONT, 9), anchor="w").pack(fill="x")
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=(px(8), 0))
            tk.Label(row, text="Continue para atualizar ou reparar. Seus saves não são tocados.", bg=CARD, fg=FG,
                     font=(FONT, 9), anchor="w").pack(side="left")
            Button(row, "Desinstalar", self._switch_to_uninstall, "danger", px).pack(side="right")

        c = card(self.body, px)
        c.pack(fill="x")
        self.rel_title = tk.Label(c, bg=CARD, fg=FG, font=(FONT, 12, "bold"), anchor="w")
        self.rel_title.pack(fill="x")
        self.rel_meta = tk.Label(c, bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w")
        self.rel_meta.pack(fill="x")
        self.rel_notes = tk.Label(c, bg=CARD, fg=FG, font=(FONT, 9), anchor="w", justify="left",
                                  wraplength=px(self.W - self.SIDE - 100))
        self.rel_notes.pack(fill="x", pady=(px(8), 0))
        self.rel_retry = Button(c, "Tentar de novo", self._fetch_release, "secondary", px)
        tips = tk.Frame(self.body, bg=PANEL)
        tips.pack(fill="x", pady=(px(16), 0))
        for line in ("Treine força, defesa, agilidade e foco em mini-games", "Enfrente 8 desafiantes na arena",
                     "160 personagens do universo UCDM", "Atualiza sozinho quando sair versão nova"):
            tk.Label(tips, text=f"★  {line}", bg=PANEL, fg=MUTED, font=(FONT, 10), anchor="w").pack(fill="x",
                                                                                              pady=px(1))
        self._refresh_release()

    def _switch_to_uninstall(self) -> None:
        self.mode = "uninstall"
        self.uninstall_target = self.existing[0] if self.existing else None
        self.root.title(f"{sc.APP_NAME} — Desinstalar")
        for i, name in enumerate(["Confirmar", "Removendo", "Pronto", "", "", ""]):
            dot, txt = self.side_steps[i]
            self.side.itemconfig(txt, text=name)
            self.side.itemconfig(dot, state="normal" if name else "hidden")
        self.side_steps = self.side_steps[:3]
        self.pages = [self.page_uninstall, self.page_progress, self.page_done]
        self.show(0)

    def _fetch_release(self) -> None:
        self.release, self.release_error = None, None
        if hasattr(self, "rel_title"):
            self._refresh_release()

        def work():
            try:
                self.q.put(("release", sc.fetch_release(self.repo)))
            except Exception as e:  # noqa: BLE001
                self.q.put(("release_error", f"{type(e).__name__}: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _refresh_release(self) -> None:
        if self.page_idx != 0 or self.mode != "install" or not self.rel_title.winfo_exists():
            return
        r = self.release
        self.rel_retry.pack_forget()
        if r:
            upd = ""
            if self.existing:
                upd = "  (você já tem esta versão)" if not rt.is_newer(r.version, self.existing[1]) else \
                    f"  (atualização da {self.existing[1]})"
            self.rel_title.config(text=f"Versão {r.version}{upd}")
            meta = [f"Download: {sc.fmt_size(r.size)}" if r.size else "", f"Publicada em {r.date}" if r.date else ""]
            self.rel_meta.config(text="  •  ".join(m for m in meta if m))
            notes = r.notes if len(r.notes) < 400 else r.notes[:400] + "…"
            self.rel_notes.config(text=notes or "Sem notas para esta versão.")
            self.b_next.set_enabled(True)
        elif self.release_error:
            self.rel_title.config(text="Não foi possível falar com o GitHub")
            self.rel_meta.config(text="Confira sua internet e tente de novo.")
            self.rel_notes.config(text=self.release_error, fg=DANGER)
            self.rel_retry.pack(anchor="w", pady=(self.px(10), 0))
            self.b_next.set_enabled(False)
        else:
            self.rel_title.config(text="Procurando a versão mais recente…")
            self.rel_meta.config(text=f"github.com/{self.repo}")
            self.rel_notes.config(text="", fg=FG)
            self.b_next.set_enabled(False)

    def page_options(self) -> None:
        px = self.px
        self.header("Onde instalar", "Escolha a pasta do jogo e o que o instalador deve criar no seu computador.")
        c = card(self.body, px)
        c.pack(fill="x")
        tk.Label(c, text="Pasta de instalação", bg=CARD, fg=FG, font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=(px(6), px(4)))
        ent = tk.Entry(row, textvariable=self.v["dir"], bg=BG, fg=FG, insertbackground=FG, relief="flat",
                       font=(FONT, 10), highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
        ent.pack(side="left", fill="x", expand=True, ipady=px(6), padx=(0, px(8)))
        Button(row, "Procurar…", self._browse, "secondary", px).pack(side="right")
        self.space_lbl = tk.Label(c, bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w")
        self.space_lbl.pack(fill="x")
        Button(c, "Usar pasta padrão", lambda: self.v["dir"].set(str(sc.default_dir())), "link", px).pack(anchor="w", pady=(px(4), 0))
        self.v["dir"].trace_add("write", lambda *a: self._check_dir())

        c2 = card(self.body, px)
        c2.pack(fill="x", pady=(px(12), 0))
        opts = [("desktop", "Atalho na Área de Trabalho", ""),
                ("start_menu", "Atalho no Menu Iniciar", "Para achar o jogo pesquisando \"UCDM\" no Iniciar."),
                ("register", "Adicionar a \"Aplicativos instalados\"",
                 "Permite desinstalar pelas Configurações do Windows.")]
        if sys.platform != "win32":
            opts = opts[:1]
        for key, title, desc in opts:
            Toggle(c2, title, desc, self.v[key], px).pack(fill="x", pady=px(5))
        self._check_dir()

    def _browse(self) -> None:
        d = filedialog.askdirectory(parent=self.root, title="Escolha onde instalar",
                                    initialdir=str(Path(self.v["dir"].get()).parent))
        if d:
            p = Path(d)
            self.v["dir"].set(str(p if p.name.lower().startswith("ucdm") else p / "UCDM"))

    def _check_dir(self) -> None:
        if not getattr(self, "space_lbl", None) or not self.space_lbl.winfo_exists():
            return
        err = sc.validate_dir(self.v["dir"].get())
        need = int((self.release.size if self.release else 30 << 20) * 1.15)
        if not err:
            free = sc.free_bytes(Path(self.v["dir"].get()))
            if free and free < need * 2:
                err = f"Espaço insuficiente: precisa de {sc.fmt_size(need * 2)}, livre {sc.fmt_size(free)}."
            else:
                self.space_lbl.config(text=f"Espaço necessário: ~{sc.fmt_size(need)}   •   "
                                           f"Disponível: {sc.fmt_size(free)}", fg=MUTED)
        if err:
            self.space_lbl.config(text=err, fg=DANGER)
        self.b_next.set_enabled(err is None)

    def page_game(self) -> None:
        px = self.px
        self.header("Configurações do jogo", "Ajuste agora ou depois. Ficam em %APPDATA%\\UCDM\\settings.json "
                                             "e valem também para atualizações futuras.")
        c = card(self.body, px)
        c.pack(fill="x")

        def row(label, widget_fn, desc=""):
            r = tk.Frame(c, bg=CARD)
            r.pack(fill="x", pady=px(5))
            t = tk.Frame(r, bg=CARD)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=label, bg=CARD, fg=FG, font=(FONT, 10, "bold"), anchor="w").pack(fill="x")
            if desc:
                tk.Label(t, text=desc, bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w").pack(fill="x")
            widget_fn(r).pack(side="right")

        row("Modo de tela", lambda r: Segmented(r, [("Janela", False), ("Tela cheia", True)], self.v["fullscreen"], px),
            "F11 alterna durante o jogo")
        row("Limite de FPS", lambda r: Segmented(
            r, [("60", "60"), ("120", "120"), ("144", "144"), ("240", "240"), ("Livre", "0")], self.v["fps_cap"], px))
        row("Volume da música", lambda r: Slider(r, self.v["music"], px))
        row("Volume dos efeitos", lambda r: Slider(r, self.v["sfx"], px))
        c2 = card(self.body, px)
        c2.pack(fill="x", pady=(px(12), 0))
        Toggle(c2, "Mostrar FPS na tela", "Contador de desempenho (F3 no jogo).", self.v["show_fps"], px).pack(
            fill="x", pady=px(4))
        Toggle(c2, "Atualizações automáticas", "Baixa e instala versões novas ao abrir o jogo.",
               self.v["auto_update"], px).pack(fill="x", pady=px(4))

    def settings(self) -> dict:
        v = self.v
        return {"display": {"fullscreen": bool(v["fullscreen"].get()),
                            "fps_cap": int(v["fps_cap"].get()), "show_fps": v["show_fps"].get()},
                "audio": {"music_volume": round(v["music"].get(), 2), "sfx_volume": round(v["sfx"].get(), 2)},
                "update": {"enabled": v["auto_update"].get()}}

    def page_summary(self) -> None:
        px = self.px
        r, v = self.release, self.v
        self.header("Tudo pronto", "Confira suas escolhas. Clique em Instalar para começar.")
        c = card(self.body, px)
        c.pack(fill="x")
        fps = v["fps_cap"].get()
        items = [
            ("Versão", f"{r.version}  ({sc.fmt_size(r.size)} para baixar)" if r else "?"),
            ("Pasta", v["dir"].get()),
            ("Atalhos", ", ".join(n for k, n in (("desktop", "Área de Trabalho"), ("start_menu", "Menu Iniciar"))
                                  if v[k].get()) or "nenhum"),
            ("Tela", f"{'Tela cheia' if v['fullscreen'].get() else 'Janela'} • "
                     f"{'sem limite de FPS' if fps == '0' else fps + ' FPS'}"),
            ("Áudio", f"Música {int(v['music'].get() * 100)}% • Efeitos {int(v['sfx'].get() * 100)}%"),
            ("Atualizações", "automáticas" if v["auto_update"].get() else "manuais (pelo instalador)"),
        ]
        for k, val in items:
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=px(3))
            tk.Label(row, text=k, bg=CARD, fg=MUTED, font=(FONT, 10), width=12, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=CARD, fg=FG, font=(FONT, 10, "bold"), anchor="w", justify="left",
                     wraplength=px(400)).pack(side="left", fill="x")
        c2 = card(self.body, px)
        c2.pack(fill="x", pady=(px(12), 0))
        Toggle(c2, "Abrir o jogo ao terminar", "", v["launch"], px).pack(fill="x")
        self.b_next.set_text("Instalar")

    # --- progresso -----------------------------------------------------------------------------
    def page_progress(self) -> None:
        px = self.px
        uninstall = self.mode == "uninstall"
        self.header("Desinstalando…" if uninstall else "Instalando…",
                    "Aguarde um instante." if uninstall else "Você pode acompanhar cada etapa abaixo.")
        self.stage_lbl = tk.Label(self.body, text="Preparando…", bg=PANEL, fg=FG, font=(FONT, 11, "bold"),
                                  anchor="w")
        self.stage_lbl.pack(fill="x")
        self.bar = ProgressBar(self.body, px)
        self.bar.pack(fill="x", pady=(px(8), px(4)))
        info = tk.Frame(self.body, bg=PANEL)
        info.pack(fill="x")
        self.pct_lbl = tk.Label(info, text="0%", bg=PANEL, fg=ACCENT, font=(FONT, 10, "bold"))
        self.pct_lbl.pack(side="left")
        self.speed_lbl = tk.Label(info, text="", bg=PANEL, fg=MUTED, font=(FONT, 9))
        self.speed_lbl.pack(side="right")
        tk.Label(self.body, text="Detalhes", bg=PANEL, fg=MUTED, font=(FONT, 9, "bold"), anchor="w").pack(
            fill="x", pady=(px(16), px(4)))
        frame = tk.Frame(self.body, bg=LINE, padx=1, pady=1)
        frame.pack(fill="both", expand=True)
        self.log_box = tk.Text(frame, bg=BG, fg=MUTED, font=("Consolas", 9), relief="flat", wrap="word",
                               padx=px(10), pady=px(8), state="disabled", height=8)
        self.log_box.pack(fill="both", expand=True)
        self.b_next.pack_forget()
        self.b_cancel.set_enabled(not uninstall)
        self.busy, self.cancel_flag, self.stage = True, False, "download"
        self._log_lines: list[str] = []
        (self._start_uninstall if uninstall else self._start_install)()
        self._animate()

    def _animate(self) -> None:
        if self.busy and self.bar.winfo_exists():
            self.bar.tick()
            self.root.after(40, self._animate)

    def log(self, msg: str) -> None:
        self.q.put(("log", msg))

    def _start_install(self) -> None:
        target = Path(self.v["dir"].get()).expanduser()
        opts = sc.InstallOptions(
            target=target, desktop_shortcut=self.v["desktop"].get(), start_menu_shortcut=self.v["start_menu"].get(),
            register=self.v["register"].get(), settings=self.settings(), log=self.log,
            progress=lambda st, f, d, t: self.q.put(("progress", st, f, d, t)), cancel=lambda: self.cancel_flag)
        self._dl = (time.perf_counter(), 0, 0.0)

        def work():
            try:
                sc.install(self.repo, self.release, opts)
                self.q.put(("done", True, ""))
            except (sc.Cancelled, InterruptedError):
                self.q.put(("done", False, "cancelled"))
            except Exception as e:  # noqa: BLE001
                self.q.put(("done", False, f"{type(e).__name__}: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _start_uninstall(self) -> None:
        target, wipe = self.uninstall_target, self.v["wipe"].get()
        self.stage_lbl.config(text="Removendo arquivos")

        def work():
            try:
                self.q.put(("progress", "install", 0.3, 0, 0))
                sc.uninstall(target, wipe, self.log) if target else sc.remove_shortcuts(self.log)
                self.q.put(("done", True, ""))
            except Exception as e:  # noqa: BLE001
                self.q.put(("done", False, f"{type(e).__name__}: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, stage: str, frac: float, done: int, total: int) -> None:
        self.stage = stage
        name, a, b = STAGES.get(stage, (stage, 0, 1))
        if self.mode == "uninstall":
            name, a, b = "Removendo arquivos", 0.0, 1.0
        overall = a + (b - a) * frac
        self.bar.set(overall)
        self.pct_lbl.config(text=f"{int(overall * 100)}%")
        self.stage_lbl.config(text=name)
        self.b_cancel.set_enabled(stage == "download")
        if stage == "download" and total:
            t0, d0, speed = self._dl
            now = time.perf_counter()
            if now - t0 >= 0.5:
                inst = (done - d0) / (now - t0)
                speed = inst if not speed else speed * 0.7 + inst * 0.3
                self._dl = (now, done, speed)
            eta = f"  •  ~{int((total - done) / speed) + 1} s restantes" if speed > 0 else ""
            self.speed_lbl.config(text=f"{sc.fmt_size(done)} de {sc.fmt_size(total)}  •  "
                                       f"{sc.fmt_size(speed)}/s{eta}" if speed else
                                  f"{sc.fmt_size(done)} de {sc.fmt_size(total)}")
        elif stage != "download":
            self.speed_lbl.config(text="")

    def _poll(self) -> None:
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "release":
                    self.release = msg[1]
                    self._refresh_release()
                elif kind == "release_error":
                    self.release_error = msg[1]
                    self._refresh_release()
                elif kind == "log":
                    if getattr(self, "log_box", None) and self.log_box.winfo_exists():
                        self.log_box.config(state="normal")
                        self.log_box.insert("end", f"› {msg[1]}\n")
                        self.log_box.see("end")
                        self.log_box.config(state="disabled")
                elif kind == "progress":
                    if getattr(self, "bar", None) and self.bar.winfo_exists():
                        self._on_progress(*msg[1:])
                elif kind == "done":
                    self.busy = False
                    self.finished_ok, self.fail_reason = msg[1], msg[2]
                    self.show(len(self.pages) - 1)
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    # --- final ---------------------------------------------------------------------------------
    def page_done(self) -> None:
        px = self.px
        self.b_back.pack_forget()
        self.b_cancel.pack_forget()
        uninstall = self.mode == "uninstall"
        box = tk.Frame(self.body, bg=PANEL)
        box.pack(fill="both", expand=True)
        cv = tk.Canvas(box, width=px(84), height=px(84), bg=PANEL, highlightthickness=0)
        cv.pack(pady=(px(20), px(12)))
        ok = self.finished_ok
        cancelled = getattr(self, "fail_reason", "") == "cancelled"
        col = OK if ok else (MUTED if cancelled else DANGER)
        cv.create_oval(px(4), px(4), px(80), px(80), outline=col, width=px(5))
        if ok:
            cv.create_line(px(24), px(44), px(37), px(57), px(61), px(30), fill=col, width=px(6), capstyle="round",
                           joinstyle="round")
        else:
            cv.create_line(px(28), px(28), px(56), px(56), fill=col, width=px(6), capstyle="round")
            cv.create_line(px(56), px(28), px(28), px(56), fill=col, width=px(6), capstyle="round")
        target = Path(self.v["dir"].get())
        if ok and uninstall:
            self.header("Desinstalado", "")
            msg = f"{sc.APP_NAME} foi removido do computador."
            if not self.v["wipe"].get():
                msg += f"\nSeus saves continuam em {sc.user_dir()} caso queira jogar de novo."
        elif ok:
            self.header("Instalação concluída!", "")
            msg = f"{sc.APP_NAME} {self.release.version} está pronto para jogar."
        elif cancelled:
            self.header("Instalação cancelada", "")
            msg = "Nada foi alterado no seu computador."
        else:
            self.header("Algo deu errado", "")
            msg = f"{self.fail_reason}\n\nSe o jogo estiver aberto, feche-o e tente de novo."
        tk.Label(box, text=msg, bg=PANEL, fg=FG if ok else MUTED, font=(FONT, 11), justify="center",
                 wraplength=px(480)).pack()
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(pady=px(18))
        if ok and not uninstall:
            Toggle(box, "Abrir o jogo agora", "", self.v["launch"], px, bg=PANEL).pack(pady=(0, px(6)))
            Button(btns, "Abrir pasta do jogo", lambda: _open_folder(target), "secondary", px).pack(side="left")
        if not ok and not uninstall:
            Button(btns, "Tentar de novo", lambda: self.show(self.pages.index(self.page_summary)), "secondary",
                   px).pack(side="left")
        self.b_next.set_text("Concluir")
        self.b_next.command = self.finish

    def finish(self) -> None:
        if self.finished_ok and self.mode == "install" and self.v["launch"].get():
            target = Path(self.v["dir"].get())
            rt.launch_detached(rt.game_command(target), target)
        self.root.destroy()

    # --- desinstalação --------------------------------------------------------------------------
    def page_uninstall(self) -> None:
        px = self.px
        t = self.uninstall_target
        self.header(f"Desinstalar {sc.APP_NAME}", "Remove o jogo, os atalhos e o registro no Windows.")
        c = card(self.body, px)
        c.pack(fill="x")
        if t:
            tk.Label(c, text=f"Versão {sc.installed_version(t) or '?'}", bg=CARD, fg=FG, font=(FONT, 11, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(c, text=str(t), bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w").pack(fill="x")
            if t.is_dir():
                tk.Label(c, text=f"Ocupa {sc.fmt_size(sc.dir_size(t))}", bg=CARD, fg=MUTED, font=(FONT, 9),
                         anchor="w").pack(fill="x")
        else:
            tk.Label(c, text="Nenhuma instalação encontrada. Serão removidos só os atalhos.", bg=CARD, fg=MUTED,
                     font=(FONT, 10), anchor="w").pack(fill="x")
        c2 = card(self.body, px)
        c2.pack(fill="x", pady=(px(12), 0))
        Toggle(c2, "Apagar também saves, mods e configurações", f"Pasta {sc.user_dir()}. Não dá para desfazer.",
               self.v["wipe"], px).pack(fill="x")
        self.b_next.set_text("Desinstalar")
        self.b_next.set_style("danger")


def _open_folder(p: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(p))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(p)])


def run(repo: str, mode: str = "install", target: Path | None = None) -> int:
    app = InstallerApp(repo, mode, target)
    app.root.mainloop()
    return 0 if app.finished_ok else 1
