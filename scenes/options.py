"""Opções: Vídeo, Áudio, Controles (rebind) e Jogo/Acessibilidade.

Tudo grava em %APPDATA%/UCDM/settings.json (só a chave alterada) e aplica na hora quando possível.
Esc/Voltar sempre sai; as teclas de "voltar" não podem ser remapeadas, então o jogador nunca fica preso.
"""
import json

import pygame

from core import paths, settings, ui
from core.scene import Scene

TABS = ("Vídeo", "Áudio", "Controles", "Jogo")
BIND_ACTIONS = (("left", "Esquerda"), ("right", "Direita"), ("up", "Cima"), ("down", "Baixo"),
                ("attack", "Atacar"), ("block", "Defender"), ("dodge", "Esquivar"), ("confirm", "Confirmar"))
RESERVED = {"escape"}
FPS_CHOICES = (30, 60, 120, 144, 0)
DIFFICULTY = (("easy", "Fácil"), ("normal", "Normal"), ("hard", "Difícil"))


def default_bindings() -> dict[str, list[str]]:
    try:
        return json.loads((paths.DATA_DIR / "game.json").read_text(encoding="utf-8"))["input"]
    except (OSError, ValueError, KeyError):
        return {}


def assign_key(bindings: dict[str, list[str]], action: str, slot: int, key: str) -> tuple[dict, str | None]:
    """Atribui `key` à ação/slot. Devolve (novo mapa, erro). Pura, para poder ser testada.

    Regras: Esc é reservado; tirar a tecla de outra ação é permitido, exceto se ela ficaria sem nenhuma.
    """
    if not key or key in RESERVED:
        return bindings, "Esc é reservado para voltar/pausar."
    new = {a: list(k) for a, k in bindings.items()}
    for other, keys in new.items():
        if other != action and key in keys:
            if len(keys) <= 1:
                return bindings, f"'{key}' é a única tecla de outra ação."
            keys.remove(key)
    mine = new.setdefault(action, [])
    while len(mine) <= slot:
        mine.append("")
    mine[slot] = key
    seen: list[str] = []
    for k in mine:       # sem repetir a mesma tecla duas vezes e sem vazios
        if k and k not in seen:
            seen.append(k)
    new[action] = seen
    return new, None


class Row:
    def __init__(self, label: str, kind: str, path: str = "", *, choices=None, lo=0.0, hi=1.0, step=0.1,
                 note: str = "", action=None, key: str = "") -> None:
        self.label, self.kind, self.path, self.choices = label, kind, path, choices
        self.lo, self.hi, self.step, self.note, self.action, self.key = lo, hi, step, note, action, key
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.slot = 0            # só para linhas de tecla (0 principal, 1 alternativa)


class OptionsScene(Scene):
    def __init__(self, game, tab: int = 0) -> None:
        super().__init__(game)
        self.tab = tab
        self.focus = 0
        self.in_tabs = False
        self.t = 0.0
        self.capturing: Row | None = None
        self.rows: list[Row] = []
        self._build()

    # --- valores --------------------------------------------------------------------------
    def _get(self, path: str, default=None):
        node = self.game.feedback.cfg if path.startswith("feedback.") else self.game.cfg
        keys = path.split(".")[1:] if path.startswith("feedback.") else path.split(".")
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def _set(self, path: str, value) -> None:
        settings.set_value(path, value)
        self.game.apply_settings()

    # --- montagem ---------------------------------------------------------------------------
    def _build(self) -> None:
        g = self.game
        if self.tab == 0:
            self.rows = [
                Row("Tela cheia", "bool", "display.fullscreen"),
                Row("Limite de FPS", "choice", "display.fps_cap", choices=[(v, "Ilimitado" if v == 0 else str(v))
                                                                          for v in FPS_CHOICES]),
                Row("VSync", "bool", "display.vsync", note="vale ao reiniciar o jogo"),
                Row("Contador de FPS", "bool", "display.show_fps", note="também no F3"),
            ]
        elif self.tab == 1:
            self.rows = [Row("Música", "slider", "audio.music_volume"), Row("Efeitos", "slider", "audio.sfx_volume")]
        elif self.tab == 2:
            self.rows = [Row(label, "bind", key=action) for action, label in BIND_ACTIONS]
            self.rows.append(Row("Restaurar teclas padrão", "action", action=self._reset_keys))
        else:
            self.rows = [
                Row("Dificuldade", "choice", "gameplay.difficulty", choices=list(DIFFICULTY),
                    note="muda dano do inimigo e janela de parry"),
                Row("Aviso do golpe (!!) mais longo", "bool", "gameplay.extended_warning"),
                Row("Pausar ao perder o foco", "bool", "gameplay.auto_pause"),
                Row("Intensidade dos efeitos", "slider", "feedback.intensity", lo=0.0, hi=1.5, step=0.25),
                Row("Tremor de tela", "bool", "feedback.screen_shake"),
                Row("Flashes de tela", "bool", "feedback.flash"),
                Row("Congelar no impacto", "bool", "feedback.hitstop"),
                Row("Reduzir movimento", "bool", "feedback.reduce_motion", note="desliga tremor, flash e câmera lenta"),
                Row("Ver tutorial", "action", action=self._help),
                Row("Créditos", "action", action=self._credits),
            ]
        if self.tab != 2:
            self.rows.append(Row("Restaurar padrões desta aba", "action", action=self._reset_tab))
        self.rows.append(Row("Voltar", "action", action=self._back))
        self.focus = min(self.focus, len(self.rows) - 1)
        compact = len(self.rows) >= 10
        y = 198 if compact else 210
        for r in self.rows:
            r.rect = pygame.Rect(150, y, 980, 38 if compact else 50)
            y += 42 if compact else 54

    # --- ações ------------------------------------------------------------------------------
    def _back(self) -> None:
        self.game.scenes.pop(fade="slide")

    def _help(self) -> None:
        from scenes.help import HelpOverlay
        self.game.scenes.push(HelpOverlay(self.game))

    def _credits(self) -> None:
        from scenes.help import CreditsOverlay
        self.game.scenes.push(CreditsOverlay(self.game))

    def _reset_tab(self) -> None:
        for r in self.rows:
            if r.path:
                settings.remove(r.path)
        self.game.apply_settings()
        self.game.feedback.toast("Padrões restaurados.", ui.GREEN)

    def _reset_keys(self) -> None:
        settings.remove("input")
        self.game.apply_settings()
        self.game.feedback.toast("Teclas restauradas.", ui.GREEN)

    def _change(self, r: Row, direction: int) -> None:
        """direction: -1/+1 (setas) ou 0 (confirmar/clicar)."""
        if r.kind == "bool":
            self._set(r.path, not bool(self._get(r.path, False)))
            ui.sfx("click")
        elif r.kind == "choice":
            vals = [c[0] for c in r.choices]
            cur = self._get(r.path)
            i = vals.index(cur) if cur in vals else 0
            self._set(r.path, vals[(i + (direction or 1)) % len(vals)])
            ui.sfx("click")
        elif r.kind == "slider" and direction:
            v = float(self._get(r.path, 0.5)) + direction * r.step
            self._set(r.path, round(max(r.lo, min(r.hi, v)), 2))
            ui.sfx("click")
        elif r.kind == "bind":
            if direction:
                r.slot = 1 - r.slot
            else:
                self.capturing = r
                self.game.input.capture = True
                self.game.input.captured = None
        elif r.kind == "action" and not direction:
            ui.sfx("confirm")
            r.action()

    def _finish_capture(self, key: str) -> None:
        r, self.capturing = self.capturing, None
        self.game.input.capture = False
        new, err = assign_key(self.game.input.bindings, r.key, r.slot, key)
        if err:
            self.game.feedback.toast(err, ui.RED)
            return
        settings.set_value("input", {a: k for a, k in new.items()})
        self.game.apply_settings()
        ui.sfx("confirm")

    def exit(self) -> None:
        self.game.input.capture = False

    # --- ciclo ------------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if self.capturing:
            if inp.captured:
                key, inp.captured = inp.captured, None
                if key == "escape":
                    self.capturing = None
                    inp.capture = False
                    self.game.feedback.toast("Esc é reservado; atribuição cancelada.", ui.ACCENT)
                else:
                    self._finish_capture(key)
            return
        if self.t < 0.15:
            return
        if inp.pressed("back"):
            ui.sfx("back")
            return self._back()
        n = len(self.rows)
        if self.in_tabs:
            if inp.pressed("left"):
                self._switch_tab((self.tab - 1) % len(TABS))
            elif inp.pressed("right"):
                self._switch_tab((self.tab + 1) % len(TABS))
            elif inp.pressed("down") or inp.pressed("confirm"):
                self.in_tabs = False
                ui.sfx("hover")
        else:
            r = self.rows[self.focus]
            if inp.pressed("down"):
                self.focus = (self.focus + 1) % n
                ui.sfx("hover")
            elif inp.pressed("up"):
                if self.focus == 0:
                    self.in_tabs = True
                else:
                    self.focus -= 1
                ui.sfx("hover")
            elif inp.pressed("left"):
                self._change(r, -1)
            elif inp.pressed("right"):
                self._change(r, +1)
            elif inp.pressed("confirm"):
                self._change(r, 0)
        # mouse/toque
        for pos in inp.taps:
            for i, rect in enumerate(self._tab_rects()):
                if rect.collidepoint(pos):
                    self._switch_tab(i)
                    return
            for i, r in enumerate(self.rows):
                if r.rect.collidepoint(pos):
                    self.in_tabs, self.focus = False, i
                    if r.kind == "slider":
                        self._drag_slider(r, pos[0])
                    elif r.kind == "bind":
                        r.slot = 0 if pos[0] < r.rect.x + 750 else 1
                        self._change(r, 0)
                    else:
                        self._change(r, 0)
                    return
        if inp.held("pointer"):
            for r in self.rows:
                if r.kind == "slider" and r.rect.collidepoint(inp.pointer_pos):
                    self._drag_slider(r, inp.pointer_pos[0])

    def _drag_slider(self, r: Row, x: float) -> None:
        track = self._slider_rect(r)
        k = max(0.0, min(1.0, (x - track.x) / track.w))
        v = round(r.lo + (r.hi - r.lo) * k / r.step) * r.step if r.step else r.lo + (r.hi - r.lo) * k
        v = round(max(r.lo, min(r.hi, v)), 2)
        if v != round(float(self._get(r.path, 0.5)), 2):
            self._set(r.path, v)

    def _switch_tab(self, i: int) -> None:
        if i != self.tab:
            self.tab, self.focus = i, 0
            self._build()
            ui.sfx("click")

    def _tab_rects(self) -> list[pygame.Rect]:
        return [pygame.Rect(150 + i * 246, 130, 236, 52) for i in range(len(TABS))]

    @staticmethod
    def _slider_rect(r: Row) -> pygame.Rect:
        return pygame.Rect(r.rect.x + 470, r.rect.centery - 8, 340, 16)

    # --- desenho ----------------------------------------------------------------------------
    def _bind_text(self, r: Row, slot: int) -> str:
        keys = self.game.input.bindings.get(r.key, [])
        return keys[slot].upper() if slot < len(keys) else "—"

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        surf.fill((22, 24, 36))
        ui.text(surf, a.font(54), "Opções", (W // 2, 40), ui.ACCENT, "midtop")
        for i, rect in enumerate(self._tab_rects()):
            sel = i == self.tab
            pygame.draw.rect(surf, (90, 80, 46) if sel else (44, 46, 62), rect, border_radius=10)
            pygame.draw.rect(surf, ui.ACCENT if (sel and self.in_tabs) else (120, 120, 140), rect,
                             3 if (sel and self.in_tabs) else 1, border_radius=10)
            ui.text(surf, a.font(28), TABS[i], rect.center, ui.WHITE if sel else (180, 180, 190), "center")
        small = a.font(18, bold=False)
        for i, r in enumerate(self.rows):
            focused = i == self.focus and not self.in_tabs
            pygame.draw.rect(surf, (60, 56, 40) if focused else (34, 36, 50), r.rect, border_radius=10)
            pygame.draw.rect(surf, ui.ACCENT if focused else (70, 72, 90), r.rect, 2 if focused else 1, border_radius=10)
            lab = ui.text(surf, a.font(26), r.label, (r.rect.x + 18, r.rect.centery), anchor="midleft")
            if r.note:
                ui.text(surf, small, r.note, (lab.right + 14, r.rect.centery), (170, 170, 180), "midleft", False)
            self._draw_value(surf, r, a)
        if self.capturing:
            dim = pygame.Surface((W, H), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 170))
            surf.blit(dim, (0, 0))
            ui.text(surf, a.font(44), f"Pressione a nova tecla para '{self.capturing.label}'", (W // 2, H // 2 - 20),
                    ui.ACCENT, "center")
            ui.text(surf, a.font(24, bold=False), "Esc cancela", (W // 2, H // 2 + 30), "white", "center")

    def _draw_value(self, surf, r: Row, a) -> None:
        font = a.font(26)
        right = r.rect.right - 20
        if r.kind == "bool":
            on = bool(self._get(r.path, False))
            box = pygame.Rect(0, 0, 80, 28)
            box.midright = (right, r.rect.centery)
            pygame.draw.rect(surf, (60, 150, 90) if on else (80, 80, 92), box, border_radius=15)
            knob_x = box.right - 16 if on else box.left + 16
            pygame.draw.circle(surf, ui.WHITE, (knob_x, box.centery), 11)
            ui.text(surf, a.font(18), "LIGADO" if on else "DESLIG.", (box.left - 12, box.centery), (200, 200, 210),
                    "midright", False)
        elif r.kind == "choice":
            cur = self._get(r.path)
            label = next((lab for v, lab in r.choices if v == cur), str(cur))
            ui.text(surf, font, f"<  {label}  >", (right, r.rect.centery), ui.ACCENT, "midright")
        elif r.kind == "slider":
            track = self._slider_rect(r)
            v = float(self._get(r.path, 0.5))
            k = (v - r.lo) / (r.hi - r.lo) if r.hi > r.lo else 0
            pygame.draw.rect(surf, (70, 72, 90), track, border_radius=8)
            fill = track.copy()
            fill.width = int(track.w * max(0.0, min(1.0, k)))
            pygame.draw.rect(surf, ui.ACCENT, fill, border_radius=8)
            pygame.draw.circle(surf, ui.WHITE, (fill.right, track.centery), 12)
            ui.text(surf, font, f"{int(round(v * 100))}%", (right, r.rect.centery), anchor="midright")
        elif r.kind == "bind":
            for slot in (0, 1):
                box = pygame.Rect(r.rect.x + 560 + slot * 200, r.rect.centery - 17, 180, 34)
                sel = slot == r.slot and r is self.rows[self.focus] and not self.in_tabs
                pygame.draw.rect(surf, (80, 70, 40) if sel else (46, 48, 66), box, border_radius=8)
                pygame.draw.rect(surf, ui.ACCENT if sel else (100, 102, 120), box, 2 if sel else 1, border_radius=8)
                ui.text(surf, a.font(22), self._bind_text(r, slot), box.center, anchor="center")
