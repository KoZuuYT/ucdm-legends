"""Overlay genérico de resultado (fim de treino, vitória/derrota)."""
from typing import Callable

import pygame

from core import ui
from core.scene import Scene
from systems.tween import ease_out_back


class ResultsOverlay(Scene):
    transparent = True
    dim_alpha = 150

    def __init__(self, game, title: str, lines: list[str], on_close: Callable[[], None],
                 color=ui.ACCENT) -> None:
        super().__init__(game)
        self.title, self.lines, self.color = title, lines, color
        self.on_close = on_close
        self.t = 0.0
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, 640, 200 + 44 * len(lines))
        self.panel.center = (W // 2, H // 2)
        self._btn_y = self.panel.bottom - 80
        self.menu = ui.Menu([ui.Button((W // 2 - 130, self._btn_y, 260, 56), "Continuar", self._close)])
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
        off = int((1 - min(1.0, ease_out_back(min(1.0, self.t / 0.3)))) * 70)   # painel "pula" para dentro
        pr = self.panel.move(0, off)
        ui.panel(surf, pr)
        f, s = self.game.assets.font(46), self.game.assets.font(28)
        ui.text(surf, f, self.title, (pr.centerx, pr.top + 30), self.color, "midtop")
        for i, line in enumerate(self.lines):   # linhas aparecem em sequência
            if self.t > 0.25 + i * 0.12:
                ui.text(surf, s, line, (pr.centerx, pr.top + 110 + i * 44), anchor="midtop")
        self.menu.buttons[0].rect.y = self._btn_y + off
        self.menu.draw(surf, s)
