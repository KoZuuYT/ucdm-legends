"""Treino de Mira (Foco): clique/toque nos alvos antes que sumam. Quanto mais
perto do centro, mais pontos. Feito para mouse e toque (ótimo no mobile)."""
import math
import random

import pygame

from core import ui
from minigames.base import TrainingGame, register


@register
class FocusTraining(TrainingGame):
    key = "focus"
    theme = "night"

    def hint(self) -> str:
        return "Clique ou toque nos alvos. No centro vale mais!"

    def virtual_buttons(self):
        return []   # o próprio toque na tela é o controle

    def spawn(self) -> None:
        r = self.ramp("radius")
        life = self.ramp("target_life") / (1 + 0.02 * (self.level - 1))
        for _ in range(10):   # evita sobrepor HUD, jogador e outros alvos
            x, y = random.uniform(120, 1160), random.uniform(130, 420)
            if all(math.hypot(o.x - x, o.y - y) > o.r + r + 10 for o in self.objs):
                break
        self.objs.spawn().reset(x=x, y=y, r=r, life=life, t=0.0)

    def handle_input(self) -> None:
        for pos in self.game.input.taps:
            hit = None
            for o in self.objs:
                d = math.hypot(o.x - pos[0], o.y - pos[1])
                if not o.done and d <= o.r and (hit is None or d < hit[1]):
                    hit = (o, d)
            if hit is None:
                self.combo = 0
                self.fx.text(pos[0], pos[1], self.small.render("FORA", True, (180, 180, 180)), 0.4)
                continue
            o, d = hit
            o.done = True
            k = d / o.r
            if k < 0.3:
                self.add_points(3, o.x, o.y, "NA MOSCA", ui.ACCENT)
            elif k < 0.65:
                self.add_points(2, o.x, o.y, "BOM", ui.WHITE)
            else:
                self.add_points(1, o.x, o.y, "RASPOU", (200, 200, 200))

    def step_objects(self, dt: float) -> None:
        for o in self.objs:
            o.t += dt
            if o.t >= o.life and not o.done:
                o.done = True
                self.fail(o.x, o.y, "ESCAPOU")

    def draw_objects(self, surf: pygame.Surface) -> None:
        for o in self.objs:
            c = (int(o.x), int(o.y))
            r = int(o.r)
            pygame.draw.circle(surf, (240, 240, 240), c, r)
            pygame.draw.circle(surf, ui.RED, c, int(r * 0.65))
            pygame.draw.circle(surf, (240, 240, 240), c, int(r * 0.3))
            remain = max(0.0, 1 - o.t / o.life)
            ring = pygame.Rect(0, 0, r * 2 + 18, r * 2 + 18)
            ring.center = c
            pygame.draw.arc(surf, ui.ACCENT, ring, math.pi / 2, math.pi / 2 + math.tau * remain, 4)
        if not self.game.input.touch_mode:
            mx, my = self.game.input.pointer_pos
            pygame.draw.circle(surf, ui.ACCENT, (int(mx), int(my)), 14, 2)
            pygame.draw.line(surf, ui.ACCENT, (mx - 20, my), (mx + 20, my), 1)
            pygame.draw.line(surf, ui.ACCENT, (mx, my - 20), (mx, my + 20), 1)
