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


# --- parallax em camadas + partículas ambiente ---------------------------------------------------
PAD = 220          # folga lateral das colinas (deslocamento máximo do parallax)
_layer_cache: dict[tuple, tuple] = {}


def _layers(theme: str, size: tuple[int, int], ground_y: int):
    key = (theme, size, ground_y)
    got = _layer_cache.get(key)
    if got is None:
        t = THEMES.get(theme, THEMES["meadow"])
        w, h = size
        sky = _gradient(size, *t["sky"])
        hills = []
        for i, c in enumerate(t["hills"]):
            surf = _hills(w + 2 * PAD, h, c, ground_y - 120 + i * 60, 60 - i * 15, seed=hash(theme) + i)
            hills.append((surf, 0.18 + 0.22 * i))       # colina de trás se move menos
        if pygame.display.get_surface():
            sky = sky.convert()
            hills = [(s.convert_alpha(), f) for s, f in hills]
        got = (sky, hills, t["ground"])
        _layer_cache[key] = got
    return got


def draw(surf: pygame.Surface, theme: str, ground_y: int, assets=None, scroll: float = 0.0, t: float = 0.0,
         parallax: bool = True) -> None:
    """Desenha o cenário. Com `parallax`, as colinas deslizam em velocidades diferentes (scroll + balanço suave
    em função de t). Arte própria em sprites/backgrounds/<tema>.png tem prioridade e fica estática."""
    size = surf.get_size()
    if not parallax or (assets is not None and assets.resolve(f"sprites/backgrounds/{theme}.png")):
        surf.blit(build(theme, size, ground_y, assets), (0, 0))
        return
    sky, hills, ground = _layers(theme, size, ground_y)
    w, h = size
    surf.blit(sky, (0, 0))
    sway = math.sin(t * 0.25) * PAD * 0.7
    for layer, factor in hills:
        off = max(-PAD, min(PAD, (scroll + sway) * factor))
        surf.blit(layer, (-PAD - off, 0))
    surf.fill(ground, (0, ground_y, w, h - ground_y))
    pygame.draw.line(surf, [max(0, v - 30) for v in ground], (0, ground_y), (w, ground_y), 4)


class Scenery:
    """Cenário de uma cena: parallax + partículas ambiente, respeitando 'reduzir movimento' e baixo desempenho."""

    def __init__(self, game, theme: str, ground_y: int, size: tuple[int, int] | None = None, ambient: bool = True) -> None:
        from systems.ambient import Ambient
        self.game, self.theme, self.ground_y = game, theme, ground_y
        size = size or (game.display.width, game.display.height)
        self.amb = Ambient(theme, size) if ambient else None

    @property
    def still(self) -> bool:
        return self.game.low_perf or self.game.feedback.reduce_motion

    def draw(self, surf: pygame.Surface, t: float, scroll: float = 0.0) -> None:
        draw(surf, self.theme, self.ground_y, self.game.assets, scroll, t, parallax=not self.still)
        self.draw_ambient(surf, t, scroll)

    def draw_ambient(self, surf: pygame.Surface, t: float, scroll: float = 0.0) -> None:
        if self.amb is not None and not self.still:
            self.amb.draw(surf, t, scroll)
