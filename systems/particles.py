"""Partículas e textos flutuantes com pool pré-alocado (zero alocação no hot path)."""
import math
import random

import pygame

from systems.pool import Pool
from systems.tween import ease_out_back, ease_out_cubic


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "gravity")

    def __init__(self) -> None:
        self.x = self.y = self.vx = self.vy = 0.0
        self.life = self.max_life = 0.0
        self.size = 4
        self.color = (255, 255, 255)
        self.gravity = 0.0


class FloatText:
    __slots__ = ("x", "y", "life", "total", "img")

    def __init__(self) -> None:
        self.x = self.y = self.life = self.total = 0.0
        self.img: pygame.Surface | None = None


class Ring:
    """Onda de choque: círculo que se expande e some."""
    __slots__ = ("x", "y", "life", "max_life", "radius", "color", "width")

    def __init__(self) -> None:
        self.x = self.y = self.life = self.max_life = self.radius = 0.0
        self.color = (255, 255, 255)
        self.width = 4


class ParticleSystem:
    def __init__(self, capacity: int = 600) -> None:
        self.parts: Pool[Particle] = Pool(Particle, capacity, grow=False)  # teto fixo de custo
        self.texts: Pool[FloatText] = Pool(FloatText, 32)
        self.rings: Pool[Ring] = Pool(Ring, 16, grow=False)
        self.scale = 1.0     # multiplicador de quantidade (intensidade de feedback / modo reduzido)

    def ring(self, x, y, color, radius=120, life=0.35, width=5) -> None:
        r = self.rings.spawn()
        if r is None:
            return
        r.x, r.y, r.color, r.radius, r.life, r.max_life, r.width = x, y, color, radius, life, life, width

    def burst(self, x, y, color, n=14, speed=260, size=5, gravity=600, life=0.5) -> None:
        for _ in range(max(0, round(n * self.scale))):
            p = self.parts.spawn()
            if p is None:
                return
            a = random.uniform(0, math.tau)
            s = random.uniform(speed * 0.3, speed)
            p.x, p.y = x, y
            p.vx, p.vy = math.cos(a) * s, math.sin(a) * s - speed * 0.3
            p.life = p.max_life = random.uniform(life * 0.6, life)
            p.size, p.color, p.gravity = size, color, gravity

    def text(self, x, y, img: pygame.Surface, life=0.9) -> None:
        t = self.texts.spawn()
        if t is None:
            return
        t.x, t.y, t.life, t.total, t.img = x, y, life, life, img

    def update(self, dt: float) -> None:
        for p in self.parts.active:
            p.life -= dt
            p.vy += p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.parts.release_where(lambda p: p.life <= 0)
        for t in self.texts.active:
            t.life -= dt
            t.y -= 60 * dt
        self.texts.release_where(lambda t: t.life <= 0)
        for r in self.rings.active:
            r.life -= dt
        self.rings.release_where(lambda r: r.life <= 0)

    def draw(self, surf: pygame.Surface, camera=None) -> None:
        w, h = surf.get_size()
        for p in self.parts.active:
            x, y = camera.to_screen(p.x, p.y) if camera else (p.x, p.y)
            if 0 <= x < w and 0 <= y < h:  # culling barato
                r = max(1, int(p.size * p.life / p.max_life))
                surf.fill(p.color, (x - r, y - r, r * 2, r * 2))
        for r in self.rings.active:
            x, y = camera.to_screen(r.x, r.y) if camera else (r.x, r.y)
            k = 1 - r.life / r.max_life
            rad = max(2, int(r.radius * ease_out_cubic(k)))
            ring = pygame.Surface((rad * 2 + 8, rad * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*r.color, int(230 * (1 - k))), (rad + 4, rad + 4), rad,
                               max(1, int(r.width * (1 - k)) + 1))
            surf.blit(ring, ring.get_rect(center=(x, y)), special_flags=pygame.BLEND_PREMULTIPLIED)
        for t in self.texts.active:
            x, y = camera.to_screen(t.x, t.y) if camera else (t.x, t.y)
            img = t.img
            age = t.total - t.life
            if age < 0.22:      # "pop": cresce passando um pouco do tamanho final
                k = 0.35 + 0.65 * ease_out_back(age / 0.22)
                img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)),
                                                         max(1, int(img.get_height() * k))))
            img.set_alpha(int(255 * min(1.0, t.life * 2)))
            surf.blit(img, img.get_rect(center=(x, y)))

    def clear(self) -> None:
        self.parts.clear()
        self.texts.clear()
        self.rings.clear()
