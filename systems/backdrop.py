"""Cenários procedurais pré-renderizados (cache) — leves e sem depender de arte.

Para trocar por arte própria: coloque assets/sprites/backgrounds/<tema>.png
e ele será usado automaticamente no lugar do procedural."""
import math
import random

import pygame

THEMES = {
    "meadow": {"sky": ((120, 190, 255), (220, 240, 255)), "hills": [(110, 170, 110), (80, 145, 85)],
               "ground": (95, 160, 80)},
    "dusk": {"sky": ((60, 50, 110), (250, 150, 110)), "hills": [(80, 70, 110), (55, 50, 85)],
             "ground": (70, 90, 70)},
    "arena": {"sky": ((90, 160, 230), (240, 220, 190)), "hills": [(150, 130, 110), (120, 100, 85)],
              "ground": (175, 150, 110)},
    "night": {"sky": ((15, 20, 45), (50, 60, 110)), "hills": [(30, 40, 70), (22, 28, 52)],
              "ground": (40, 55, 60)},
}

_cache: dict[tuple, pygame.Surface] = {}


def _gradient(size, top, bottom) -> pygame.Surface:
    w, h = size
    col = pygame.Surface((1, h))
    for y in range(h):
        k = y / max(h - 1, 1)
        col.set_at((0, y), [int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)])
    return pygame.transform.scale(col, (w, h))


def _hills(w, h, color, base_y, amp, seed) -> pygame.Surface:
    rnd = random.Random(seed)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    f1, f2 = rnd.uniform(1.5, 3), rnd.uniform(4, 7)
    p1, p2 = rnd.uniform(0, 6), rnd.uniform(0, 6)
    pts = [(0, h)]
    for x in range(0, w + 16, 16):
        t = x / w * math.tau
        pts.append((x, base_y - amp * (0.6 * math.sin(t * f1 + p1) + 0.4 * math.sin(t * f2 + p2))))
    pts.append((w, h))
    pygame.draw.polygon(s, color, pts)
    return s


def build(theme: str, size: tuple[int, int], ground_y: int, assets=None) -> pygame.Surface:
    key = (theme, size, ground_y)
    if key in _cache:
        return _cache[key]
    if assets is not None and assets.resolve(f"sprites/backgrounds/{theme}.png"):
        surf = pygame.transform.smoothscale(assets.image(f"sprites/backgrounds/{theme}.png"), size).convert()
    else:
        t = THEMES.get(theme, THEMES["meadow"])
        w, h = size
        surf = _gradient(size, *t["sky"])
        for i, c in enumerate(t["hills"]):
            surf.blit(_hills(w, h, c, ground_y - 120 + i * 60, 60 - i * 15, seed=hash(theme) + i), (0, 0))
        surf.fill(t["ground"], (0, ground_y, w, h - ground_y))
        pygame.draw.line(surf, [max(0, v - 30) for v in t["ground"]], (0, ground_y), (w, ground_y), 4)
        if pygame.display.get_surface():
            surf = surf.convert()
    _cache[key] = surf
    return surf
