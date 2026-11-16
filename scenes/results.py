"""Overlay genérico de resultado (fim de treino, vitória/derrota)."""
from typing import Callable

import pygame

from core import ui
from core.scene import Scene


class ResultsOverlay(Scene):
    transparent = True

    def __init__(self, game, title: str, lines: list[str], on_close: Callable[[], None],
                 color=ui.ACCENT) -> None:
        super().__init__(game)
        self.title, self.lines, self.color = title, lines, color
        self.on_close = on_close
        self.t = 0.0
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, 640, 200 + 44 * len(lines))
        self.panel.center = (W // 2, H // 2)
        self.menu = ui.Menu([ui.Button((W // 2 - 130, self.panel.bottom - 80, 260, 56), "Continuar", self._close)])
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 150))

    def _close(self) -> None:
        self.game.scenes.pop()
        self.on_close()

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t > 0.4:   # evita fechar sem querer com a tecla que encerrou o treino
            self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        ui.panel(surf, self.panel)
        f, s = self.game.assets.font(46), self.game.assets.font(28)
        ui.text(surf, f, self.title, (self.panel.centerx, self.panel.top + 30), self.color, "midtop")
        for i, line in enumerate(self.lines):
            ui.text(surf, s, line, (self.panel.centerx, self.panel.top + 110 + i * 44), anchor="midtop")
        self.menu.draw(surf, s)
