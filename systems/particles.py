"""Partículas, ondas de choque, estrelas de impacto e textos flutuantes, com pools pré-alocados.

Formas de partícula: quadradinho (padrão), `streak` (risco na direção do movimento: faíscas de impacto) e
`puff` (nuvem que cresce e some: poeira ao andar/esquivar/aterrissar).
"""
import math
import random

import pygame

from systems.pool import Pool
from systems.tween import ease_out_back, ease_out_cubic

SQUARE, STREAK, PUFF = 0, 1, 2


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "gravity", "kind")

    def __init__(self) -> None:
        self.x = self.y = self.vx = self.vy = 0.0
        self.life = self.max_life = 0.0
        self.size = 4
        self.color = (255, 255, 255)
        self.gravity = 0.0
        self.kind = SQUARE


class FloatText:
    __slots__ = ("x", "y", "life", "total", "img")

    def __init__(self) -> None:
        self.x = self.y = self.life = self.total = 0.0
        self.img: pygame.Surface | None = None


class Ring:
    """Onda de choque (círculo que se expande) ou estrela de impacto (`star`)."""
    __slots__ = ("x", "y", "life", "max_life", "radius", "color", "width", "star")

    def __init__(self) -> None:
        self.x = self.y = self.life = self.max_life = self.radius = 0.0
        self.color = (255, 255, 255)
        self.width = 4
        self.star = False


class ParticleSystem:
    def __init__(self, capacity: int = 600) -> None:
        self.parts: Pool[Particle] = Pool(Particle, capacity, grow=False)  # teto fixo de custo
        self.texts: Pool[FloatText] = Pool(FloatText, 32)
        self.rings: Pool[Ring] = Pool(Ring, 24, grow=False)
        self.scale = 1.0     # multiplicador de quantidade (intensidade de feedback / modo reduzido)

    def ring(self, x, y, color, radius=120, life=0.35, width=5, star=False) -> None:
        r = self.rings.spawn()
        if r is None:
            return
        r.x, r.y, r.color, r.radius, r.life, r.max_life, r.width, r.star = x, y, color, radius, life, life, width, star

    def star(self, x, y, color, size=100, life=0.25) -> None:
        """Estrela de impacto (8 pontas) que estoura e some: o "POW" do golpe."""
        if self.scale > 0:
            self.ring(x, y, color, radius=size, life=life, width=0, star=True)

    def burst(self, x, y, color, n=14, speed=260, size=5, gravity=600, life=0.5, streak=False, direction=None) -> None:
        """Explosão de partículas. `streak` desenha riscos; `direction` (+1/-1) inclina o leque para esse lado."""
        for _ in range(max(0, round(n * self.scale))):
            p = self.parts.spawn()
            if p is None:
                return
            if direction is None:
                a = random.uniform(0, math.tau)
            else:
                a = random.uniform(-1.0, 1.0) + (0 if direction > 0 else math.pi)
            s = random.uniform(speed * 0.3, speed)
            p.x, p.y = x, y
            p.vx, p.vy = math.cos(a) * s, math.sin(a) * s - (0 if streak else speed * 0.3)
            p.life = p.max_life = random.uniform(life * 0.6, life)
            p.size, p.color, p.gravity = size, color, gravity * (0.4 if streak else 1.0)
            p.kind = STREAK if streak else SQUARE

    def puff(self, x, y, color, n=4, size=16) -> None:
        """Nuvens de poeira: sobem devagar, crescem e somem."""
        for _ in range(max(0, round(n * max(self.scale, 0.0)))):
            p = self.parts.spawn()
            if p is None:
                return
            p.x, p.y = x + random.uniform(-12, 12), y + random.uniform(-4, 4)
            p.vx, p.vy = random.uniform(-70, 70), random.uniform(-60, -10)
            p.life = p.max_life = random.uniform(0.35, 0.6)
            p.size, p.color, p.gravity, p.kind = size * random.uniform(0.7, 1.2), color, 0.0, PUFF

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
            if p.kind == PUFF:
                p.vx *= 1 - 2.0 * dt
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
            if not (-40 <= x < w + 40 and -40 <= y < h + 40):  # culling barato
                continue
            k = p.life / p.max_life
            if p.kind == STREAK:
                tail = 0.045
                pygame.draw.line(surf, p.color, (x, y), (x - p.vx * tail, y - p.vy * tail), max(2, int(p.size * k)))
            elif p.kind == PUFF:
                rad = int(p.size * (1.0 + 1.4 * (1 - k)))
                cloud = pygame.Surface((rad * 2 + 2, rad * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(cloud, (*p.color, int(120 * k)), (rad + 1, rad + 1), rad)
                surf.blit(cloud, cloud.get_rect(center=(x, y)))
            else:
                r = max(1, int(p.size * k))
                surf.fill(p.color, (x - r, y - r, r * 2, r * 2))
        for r in self.rings.active:
            x, y = camera.to_screen(r.x, r.y) if camera else (r.x, r.y)
            k = 1 - r.life / r.max_life
            if r.star:
                self._draw_star(surf, x, y, r, k)
                continue
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

    @staticmethod
    def _draw_star(surf: pygame.Surface, x: float, y: float, r: Ring, k: float) -> None:
        """Estrela de 8 pontas (pontas longas e curtas alternadas) que cresce rápido e some."""
        size = max(6, int(r.radius * (0.35 + 0.65 * ease_out_cubic(min(1.0, k * 2)))))
        alpha = int(235 * (1 - k) ** 1.4)
        spikes = 8
        pts = []
        spin = k * 0.6
        for i in range(spikes * 2):
            ang = math.pi * i / spikes + spin
            rad = size if i % 2 == 0 else size * 0.28
            pts.append((size + 2 + math.cos(ang) * rad, size + 2 + math.sin(ang) * rad))
        star = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
        pygame.draw.polygon(star, (*r.color, alpha), pts)
        pygame.draw.polygon(star, (255, 255, 255, alpha), [(size + 2 + (px - size - 2) * 0.55, size + 2 + (py - size - 2) * 0.55)
                                                           for px, py in pts])
        surf.blit(star, star.get_rect(center=(x, y)), special_flags=pygame.BLEND_PREMULTIPLIED)

    def clear(self) -> None:
        self.parts.clear()
        self.texts.clear()
        self.rings.clear()
