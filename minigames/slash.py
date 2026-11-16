"""Treino de Golpe (Força): alvos vêm de 3 direções; aperte a direção quando
o alvo estiver dentro do anel. Blocos-bomba devem ser deixados passar."""
import math
import random

import pygame

from core import ui
from minigames.base import Obj, TrainingGame, register

DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1)}


@register
class SlashTraining(TrainingGame):
    key = "slash"
    theme = "meadow"

    def __init__(self, game) -> None:
        super().__init__(game)
        px, py = self.PLAYER_POS
        self.center = pygame.Vector2(px, py - 100)        # "peito" do personagem
        hz = self.cfg["hit_zone"]
        self.zones = {d: self.center + pygame.Vector2(v) * hz for d, v in DIRS.items()}
        self.swing: tuple[str, float] | None = None

    def hint(self) -> str:
        return "Setas/WASD ou deslize quando o alvo entrar no anel. Não acerte os blocos pretos!"

    def spawn(self) -> None:
        d = random.choice(list(DIRS))
        dx, dy = DIRS[d]
        start = self.center + pygame.Vector2(dx, dy) * 760
        speed = self.ramp("speed", level_scaled=True)
        kind = "bomb" if random.random() < self.cfg["bomb_chance"] else "normal"
        self.objs.spawn().reset(x=start.x, y=start.y, vx=-dx * speed, vy=-dy * speed, dir=d, kind=kind, r=30)

    def _dist_along(self, o: Obj) -> float:
        """Distância (com sinal) do alvo ao centro do anel, ao longo da sua direção."""
        dx, dy = DIRS[o.dir]
        z = self.zones[o.dir]
        return (o.x - z.x) * dx + (o.y - z.y) * dy

    def handle_input(self) -> None:
        d = self.game.input.pressed_direction()
        if d not in DIRS:
            return
        self.swing = (d, 0.12)
        size, perfect = self.cfg["zone_size"], self.cfg["perfect_size"]
        best = None
        for o in self.objs:
            if o.dir == d and not o.done and abs(self._dist_along(o)) <= size:
                if best is None or abs(self._dist_along(o)) < abs(self._dist_along(best)):
                    best = o
        if best is None:
            self.combo = 0
            return
        best.done = True
        if best.kind == "bomb":
            self.fail(best.x, best.y, "BOMBA!")
        elif abs(self._dist_along(best)) <= perfect:
            self.add_points(2, best.x, best.y, "PERFEITO")
        else:
            self.add_points(1, best.x, best.y, "BOM", ui.WHITE)

    def step_objects(self, dt: float) -> None:
        if self.swing:
            self.swing = (self.swing[0], self.swing[1] - dt) if self.swing[1] > dt else None
        for o in self.objs:
            o.x += o.vx * dt
            o.y += o.vy * dt
            o.t += dt
            if self._dist_along(o) < -self.cfg["zone_size"]:   # passou do anel
                o.done = True
                if o.kind == "normal":
                    self.fail(o.x, o.y)

    def draw_objects(self, surf: pygame.Surface) -> None:
        size = self.cfg["zone_size"]
        for d, z in self.zones.items():
            pygame.draw.circle(surf, (255, 255, 255), z, size, 3)
            pygame.draw.circle(surf, (255, 255, 255), z, self.cfg["perfect_size"], 1)
        for o in self.objs:
            r = int(o.r)
            rect = pygame.Rect(0, 0, r * 2, r * 2)
            rect.center = (int(o.x), int(o.y))
            if o.kind == "bomb":
                pygame.draw.rect(surf, (25, 25, 30), rect)
                pygame.draw.line(surf, ui.RED, rect.topleft, rect.bottomright, 5)
                pygame.draw.line(surf, ui.RED, rect.topright, rect.bottomleft, 5)
            else:
                pygame.draw.rect(surf, (176, 120, 66), rect)
                pygame.draw.rect(surf, (120, 78, 40), rect, 5)
                pygame.draw.rect(surf, (220, 60, 50), rect.inflate(-36, -36))
        if self.swing:
            d, t = self.swing
            z = self.zones[d]
            a = {"left": math.pi, "right": 0.0, "up": math.pi / 2}[d]
            arc = pygame.Rect(0, 0, 200, 200)
            arc.center = (int(self.center.x), int(self.center.y))
            pygame.draw.arc(surf, (255, 250, 220), arc, a - 0.7, a + 0.7, 10)
            pygame.draw.circle(surf, ui.ACCENT, z, 10)
