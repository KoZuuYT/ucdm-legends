"""Diálogos modais: confirmação (com opção de "segurar para confirmar") e entrada de texto.

Regra de segurança: o foco começa em "Cancelar". Ação destrutiva pode exigir segurar o botão (hold).
"""
from typing import Callable

import pygame

from core import ui
from core.scene import Scene
from systems.tween import ease_out_back


class _Modal(Scene):
    transparent = True
    GRACE = 0.25           # ignora a tecla que abriu o diálogo

    def __init__(self, game, size: tuple[int, int]) -> None:
        super().__init__(game)
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, *size)
        self.panel.center = (W // 2, H // 2)
        self.t = 0.0
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))

    @property
    def pop(self) -> float:
        """0..1 (passa um pouco de 1): animação de entrada do painel."""
        return ease_out_back(min(1.0, self.t / 0.28))

    def _offset(self) -> int:
        return int((1 - min(1.0, self.pop)) * 50)

    def _close(self) -> None:
        self.game.scenes.pop()


class ConfirmDialog(_Modal):
    def __init__(self, game, title: str, message: str, on_yes: Callable[[], None], *, yes_label: str = "Sim",
                 no_label: str = "Cancelar", hold: float = 0.0, danger: bool = False) -> None:
        super().__init__(game, (640, 300))
        self.title, self.message, self.on_yes = title, message, on_yes
        self.hold, self.prog, self.danger = hold, 0.0, danger
        y = self.panel.bottom - 84
        self.yes = ui.Button((self.panel.x + 40, y, 270, 58), yes_label, lambda: None)
        self.no = ui.Button((self.panel.right - 310, y, 270, 58), no_label, lambda: None)
        self.focus = 1                     # começa em Cancelar

    def _yes(self) -> None:
        self._close()
        self.on_yes()

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if self.t < self.GRACE:
            return
        if inp.pressed("back"):
            ui.sfx("back")
            return self._close()
        if inp.pressed("left") or inp.pressed("right"):
            self.focus = 1 - self.focus
            ui.sfx("hover")
        if self.hold > 0:
            holding = (self.focus == 0 and inp.held("confirm")) or (
                inp.held("pointer") and self.yes.rect.collidepoint(inp.pointer_pos))
            self.prog = self.prog + dt if holding else max(0.0, self.prog - dt * 2)
            if self.prog >= self.hold:
                return self._yes()
        elif inp.pressed("confirm") and self.focus == 0:
            ui.sfx("confirm")
            return self._yes()
        if inp.pressed("confirm") and self.focus == 1:
            ui.sfx("back")
            return self._close()
        for pos in inp.taps:
            if self.no.rect.collidepoint(pos):
                ui.sfx("back")
                return self._close()
            if self.hold <= 0 and self.yes.rect.collidepoint(pos):
                ui.sfx("confirm")
                return self._yes()

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        off = self._offset()
        a = self.game.assets
        pr = self.panel.move(0, off)
        ui.panel(surf, pr, (20, 22, 32, 240))
        ui.text(surf, a.font(40), self.title, (pr.centerx, pr.top + 26), ui.RED if self.danger else ui.ACCENT, "midtop")
        for i, line in enumerate(self.message.split("\n")):
            ui.text(surf, a.font(24, bold=False), line, (pr.centerx, pr.top + 92 + i * 30), anchor="midtop")
        for b in (self.yes, self.no):
            b.rect.y = self.panel.bottom - 84 + off
        if self.hold > 0:
            self.yes.sub = "segure" if self.prog <= 0 else ""
        self.yes.draw(surf, a.font(28), self.focus == 0, a.font(16))
        self.no.draw(surf, a.font(28), self.focus == 1)
        if self.hold > 0 and self.prog > 0:
            ui.bar(surf, (self.yes.rect.x, self.yes.rect.bottom + 6, self.yes.rect.w, 8), self.prog / self.hold,
                   ui.RED, border=ui.RED)


class TextPrompt(_Modal):
    """Entrada de texto simples (ex.: nome do treinador). Usa o teclado cru: Enter confirma, Esc cancela."""

    def __init__(self, game, title: str, initial: str, on_ok: Callable[[str], None], *, max_len: int = 16,
                 hint: str = "Enter confirma  ·  Esc cancela") -> None:
        super().__init__(game, (640, 280))
        self.title, self.text, self.on_ok, self.max_len, self.hint = title, initial, on_ok, max_len, hint
        y = self.panel.bottom - 80
        self.ok = ui.Button((self.panel.x + 40, y, 270, 54), "Salvar", lambda: None)
        self.cancel = ui.Button((self.panel.right - 310, y, 270, 54), "Cancelar", lambda: None)
        self._prev = set()

    def enter(self) -> None:
        try:
            pygame.key.start_text_input()
        except (AttributeError, pygame.error):
            pass

    def exit(self) -> None:
        try:
            pygame.key.stop_text_input()
        except (AttributeError, pygame.error):
            pass

    def _submit(self) -> None:
        self._close()
        self.on_ok(self.text.strip())

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        keys = pygame.key.get_pressed()
        now = {k for k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_BACKSPACE) if keys[k]}
        fresh, self._prev = now - self._prev, now
        for ch in inp.text_input:                  # texto digitado neste frame
            if ch.isprintable() and len(self.text) < self.max_len:
                self.text += ch
        if self.t < self.GRACE:
            return
        if pygame.K_BACKSPACE in fresh:
            self.text = self.text[:-1]
        if pygame.K_ESCAPE in fresh:
            ui.sfx("back")
            return self._close()
        if fresh & {pygame.K_RETURN, pygame.K_KP_ENTER}:
            ui.sfx("confirm")
            return self._submit()
        for pos in inp.taps:
            if self.cancel.rect.collidepoint(pos):
                ui.sfx("back")
                return self._close()
            if self.ok.rect.collidepoint(pos):
                ui.sfx("confirm")
                return self._submit()

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        off = self._offset()
        a = self.game.assets
        pr = self.panel.move(0, off)
        ui.panel(surf, pr, (20, 22, 32, 240))
        ui.text(surf, a.font(36), self.title, (pr.centerx, pr.top + 22), ui.ACCENT, "midtop")
        box = pygame.Rect(0, 0, 520, 56)
        box.center = (pr.centerx, pr.top + 130)
        pygame.draw.rect(surf, (34, 36, 52), box, border_radius=8)
        pygame.draw.rect(surf, ui.ACCENT, box, 2, border_radius=8)
        caret = "_" if int(self.t * 2) % 2 == 0 else " "
        ui.text(surf, a.font(32), self.text + caret, (box.x + 16, box.centery), anchor="midleft")
        ui.text(surf, a.font(16, bold=False), self.hint, (pr.centerx, box.bottom + 10), (190, 190, 200), "midtop")
        for b in (self.ok, self.cancel):
            b.rect.y = self.panel.bottom - 80 + off
        self.ok.draw(surf, a.font(26), True)
        self.cancel.draw(surf, a.font(26), False)
