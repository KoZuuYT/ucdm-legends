"""Treino de Escudo (Defesa): projéteis vêm de 3 direções. Segure a direção
para posicionar o escudo; apertar logo antes do impacto vale um PARRY (x2)."""
import random

import pygame

from core import ui
from minigames.base import TrainingGame, register

DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1)}
SHIELD_DIST = 95


@register
class ShieldTraining(TrainingGame):
    key = "shield"
    theme = "dusk"

    def __init__(self, game) -> None:
        super().__init__(game)
        px, py = self.PLAYER_POS
        self.center = pygame.Vector2(px, py - 100)
        self.last_press: dict[str, float] = {d: -9.0 for d in DIRS}
        self.guard = "left"

    def hint(self) -> str:
        return "Segure a direção do projétil. Aperte no último instante para PARRY!"

    def spawn(self) -> None:
        d = random.choice(list(DIRS))
        dx, dy = DIRS[d]
        start = self.center + pygame.Vector2(dx, dy) * 760
        speed = self.ramp("speed", level_scaled=True)
        self.objs.spawn().reset(x=start.x, y=start.y, vx=-dx * speed, vy=-dy * speed, dir=d, r=12)

    def handle_input(self) -> None:
        d = self.game.input.pressed_direction()
        if d in DIRS:
            self.last_press[d] = self.elapsed
        held = self.game.input.held_direction()
        if held in DIRS:
            self.guard = held

    def step_objects(self, dt: float) -> None:
        for o in self.objs:
            o.x += o.vx * dt
            o.y += o.vy * dt
            if (pygame.Vector2(o.x, o.y) - self.center).length() <= SHIELD_DIST:
                o.done = True
                held = self.game.input.held_direction()
                if held == o.dir:
                    if self.elapsed - self.last_press[o.dir] <= self.cfg["parry_window"]:
                        self.add_points(2, o.x, o.y, "PARRY", ui.ACCENT)
                        self.game.audio.play("parry")
                    else:
                        self.add_points(1, o.x, o.y, "BLOQUEIO", ui.BLUE)
                        self.game.audio.play("block")
                else:
                    self.fail(o.x, o.y, "AI!")

    def draw_objects(self, surf: pygame.Surface) -> None:
        held = self.game.input.held_direction()
        d = held if held in DIRS else self.guard
        dx, dy = DIRS[d]
        pos = self.center + pygame.Vector2(dx, dy) * SHIELD_DIST
        rect = pygame.Rect(0, 0, 24 if dx else 120, 120 if dx else 24)
        rect.center = (int(pos.x), int(pos.y))
        col = (120, 170, 255) if held in DIRS else (80, 90, 120)
        pygame.draw.rect(surf, col, rect, border_radius=10)
        pygame.draw.rect(surf, (230, 240, 255), rect, 3, border_radius=10)
        for o in self.objs:
            tail = pygame.Vector2(o.x, o.y) - pygame.Vector2(o.vx, o.vy).normalize() * 60
            pygame.draw.line(surf, (90, 60, 40), tail, (o.x, o.y), 6)
            pygame.draw.circle(surf, (210, 210, 220), (int(o.x), int(o.y)), 9)
