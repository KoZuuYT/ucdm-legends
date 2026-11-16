"""Pausa (Esc ou janela sem foco) para treinos e arena."""
from typing import Callable

import pygame

from core import ui
from core.scene import Scene
from scenes.dialogs import ConfirmDialog
from systems.tween import ease_out_cubic


class PauseOverlay(Scene):
    transparent = True
    GRACE = 0.2

    def __init__(self, game, on_quit: Callable[[], None]) -> None:
        super().__init__(game)
        self.on_quit = on_quit
        self.t = 0.0
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, 460, 400)
        self.panel.center = (W // 2, H // 2)
        x, w = self.panel.x + 50, self.panel.w - 100
        self.menu = ui.Menu([
            ui.Button((x, self.panel.y + 110, w, 58), "Continuar", self._resume),
            ui.Button((x, self.panel.y + 184, w, 58), "Opções", self._options),
            ui.Button((x, self.panel.y + 258, w, 58), "Desistir", self._quit),
        ])
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 150))

    def _resume(self) -> None:
        self.game.scenes.pop()

    def _options(self) -> None:
        from scenes.options import OptionsScene
        self.game.scenes.push(OptionsScene(self.game), fade="slide")

    def _quit(self) -> None:
        self.game.scenes.push(ConfirmDialog(
            self.game, "Desistir?", "O treino/luta atual termina sem recompensa.\nSeu progresso salvo não é afetado.",
            on_yes=self._do_quit, yes_label="Desistir", danger=True))

    def _do_quit(self) -> None:
        self.game.scenes.pop()      # fecha a pausa
        self.on_quit()

    def update(self, dt: float) -> None:
        self.t += dt
        self.game.audio.duck(0.3)      # música mais baixa enquanto pausado
        if self.t < self.GRACE:
            return
        if self.game.input.pressed("back"):
            ui.sfx("back")
            return self._resume()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        k = ease_out_cubic(min(1.0, self.t / 0.2))
        off = int((1 - k) * 40)
        a = self.game.assets
        ui.panel(surf, self.panel.move(0, off), (20, 22, 32, 235))
        ui.text(surf, a.font(48), "PAUSADO", (self.panel.centerx, self.panel.top + 26 + off), ui.ACCENT, "midtop")
        for b, base in zip(self.menu.buttons, (110, 184, 258)):
            b.rect.y = self.panel.y + base + off
        self.menu.draw(surf, a.font(30))
