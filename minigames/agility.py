"""Treino de Esquiva (Agilidade): obstáculos baixos (pule com CIMA) e altos
(abaixe com BAIXO) vêm dos dois lados. Esquiva no limite vale x2."""
import random

import pygame

from core import ui
from minigames.base import TrainingGame, register

LOW_Y, HIGH_Y = 525, 390


@register
class AgilityTraining(TrainingGame):
    key = "agility"
    theme = "meadow"

    def __init__(self, game) -> None:
        super().__init__(game)
        self.pose = "stand"
        self.pose_t = 0.0
        self.pose_started = -9.0

    def hint(self) -> str:
        return "CIMA pula obstáculos baixos, BAIXO desvia dos altos."

    def spawn(self) -> None:
        side = random.choice((-1, 1))
        high = random.random() < 0.5
        speed = self.ramp("speed", level_scaled=True)
        self.objs.spawn().reset(x=640 + side * 720, y=HIGH_Y if high else LOW_Y, vx=-side * speed,
                                kind="high" if high else "low", r=34)

    def handle_input(self) -> None:
        inp = self.game.input
        for action, pose in (("up", "jump"), ("down", "duck")):
            if inp.pressed(action):
                self.pose, self.pose_t, self.pose_started = pose, self.cfg["pose_time"], self.elapsed

    def step_objects(self, dt: float) -> None:
        self.pose_t -= dt
        if self.pose_t <= 0:
            self.pose = "stand"
        px = self.PLAYER_POS[0]
        for o in self.objs:
            prev = o.x
            o.x += o.vx * dt
            o.t += dt
            if (prev - px) * (o.x - px) <= 0:      # cruzou a posição do jogador
                o.done = True
                ok = (o.kind == "low" and self.pose == "jump") or (o.kind == "high" and self.pose == "duck")
                if ok:
                    close = self.elapsed - self.pose_started <= 0.18
                    self.add_points(2 if close else 1, o.x, o.y, "NO LIMITE" if close else "DESVIOU",
                                    ui.ACCENT if close else ui.GREEN)
                else:
                    self.fail(o.x, o.y, "PANCADA!")

    def draw_player(self, surf: pygame.Surface) -> None:
        img = self.game.assets.image_h(self.char["sprite"], self.PLAYER_H, self.player_flip)
        x, y = self.PLAYER_POS
        if self.pose == "jump":
            k = max(0.0, self.pose_t / self.cfg["pose_time"])
            y -= int(150 * 4 * k * (1 - k) + 40)
        elif self.pose == "duck":
            w, h = img.get_size()
            img = pygame.transform.scale(img, (int(w * 1.15), int(h * 0.5)))
        surf.blit(img, img.get_rect(midbottom=(x, y)))

    def draw_objects(self, surf: pygame.Surface) -> None:
        for o in self.objs:
            r = int(o.r)
            if o.kind == "low":
                pygame.draw.circle(surf, (120, 120, 130), (int(o.x), int(o.y)), r)
                pygame.draw.circle(surf, (70, 70, 80), (int(o.x), int(o.y)), r, 5)
            else:
                rect = pygame.Rect(0, 0, r * 3, r)
                rect.center = (int(o.x), int(o.y))
                pygame.draw.rect(surf, (150, 90, 50), rect, border_radius=8)
                pygame.draw.rect(surf, (90, 50, 30), rect, 4, border_radius=8)
