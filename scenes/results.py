"""Overlay genérico de resultado (fim de treino, vitória/derrota)."""
import math
import random
import re
from typing import Callable

import pygame

from core import ui
from core.scene import Scene
from systems.tween import ease_out_back


class ResultsOverlay(Scene):
    transparent = True
    dim_alpha = 150

    def __init__(self, game, title: str, lines: list[str], on_close: Callable[[], None],
                 color=ui.ACCENT, grade: str | None = None) -> None:
        super().__init__(game)
        self.title, self.lines, self.color = title, lines, color
        self.grade = grade
        self.on_close = on_close
        self.t = 0.0
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, 640, 200 + 44 * len(lines))
        self.panel.center = (W // 2, H // 2)
        self._btn_y = self.panel.bottom - 80
        self.menu = ui.Menu([ui.Button((W // 2 - 130, self._btn_y, 260, 56), "Continuar", self._close)])
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 150))
        m = re.search(r"\+(\d+)", " ".join(lines))
        self.gold = int(m.group(1)) if m else 0
        rnd = random.Random(len(title) + self.gold)
        # orbes de XP: saem do painel e voam para o canto do contador de ouro/XP (decorativo)
        self.orbs = [{"t0": 0.5 + i * 0.05, "x": self.panel.centerx + rnd.uniform(-120, 120), "y": self.panel.top + 130 + rnd.uniform(0, 80),
                      "a": rnd.uniform(0, 6.28)} for i in range(min(24, self.gold // 2))]

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
                if self.gold and re.search(r"\+\d+", line):          # contador de ouro sobe animado
                    k = min(1.0, (self.t - 0.4 - i * 0.12) / 0.8)
                    line = re.sub(r"\+\d+", "+" + str(int(self.gold * max(0.0, k))), line, count=1)
                ui.text(surf, s, line, (pr.centerx, pr.top + 110 + i * 44), anchor="midtop")
        if self.grade and self.t > 0.9:         # carimbo da nota: entra grande e "bate" no painel
            from systems import grading
            k = min(1.0, (self.t - 0.9) / 0.25)
            size = int(150 - 60 * k)
            img = ui._heading(self.game.assets.font(size), self.grade, grading.GRADE_COLORS[self.grade])
            img = pygame.transform.rotozoom(img, 12, 1.0)
            img.set_alpha(int(255 * k))
            surf.blit(img, img.get_rect(center=(pr.right - 110, pr.top + 150 + off)))
        if not self.game.feedback.reduce_motion:
            for o in self.orbs:
                k = (self.t - o["t0"]) / 0.9
                if 0 <= k < 1:
                    e = k * k
                    x = o["x"] + (60 - o["x"]) * e + math.sin(o["a"] + k * 6) * 18 * (1 - k)
                    y = o["y"] + (40 - o["y"]) * e
                    sz = 5 + int(2 * math.sin(self.t * 20 + o["a"]))
                    pygame.draw.rect(surf, (150, 235, 40), (x - sz, y - sz, 2 * sz, 2 * sz))
                    pygame.draw.rect(surf, (230, 255, 120), (x - sz // 2, y - sz // 2, sz, sz))
        self.menu.buttons[0].rect.y = self._btn_y + off
        self.menu.draw(surf, s)
