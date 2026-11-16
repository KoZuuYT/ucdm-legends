"""Partículas ambiente por tema (pólen, vaga-lumes, poeira, estrelas). Totalmente determinísticas
(posição = função do tempo), então não alocam nada por frame; os brilhos são sprites pré-renderizados."""
import math
import random

import pygame

# tipo, quantidade, cor, tamanho (raio do brilho), velocidade horizontal, balanço vertical
THEMES = {
    "meadow": ("pollen", 26, (255, 250, 190), 5, 14, 22),
    "dusk": ("firefly", 24, (255, 215, 120), 6, 8, 30),
    "arena": ("dust", 30, (230, 205, 160), 4, 26, 10),
    "night": ("firefly", 30, (170, 210, 255), 5, 6, 26),
}

_glow_cache: dict[tuple, pygame.Surface] = {}


def _glow(color, r: int) -> pygame.Surface:
    key = (color, r)
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((r * 4, r * 4))
        for i in range(r * 2, 0, -1):          # círculos concêntricos: do escuro (borda) ao claro (centro)
            k = (1 - i / (r * 2)) ** 1.6
            pygame.draw.circle(g, tuple(int(c * k) for c in color), (r * 2, r * 2), i)
        _glow_cache[key] = g
    return g


class Ambient:
    def __init__(self, theme: str, size: tuple[int, int], seed: int = 0) -> None:
        self.size = size
        spec = THEMES.get(theme, THEMES["meadow"])
        self.kind, n, self.color, self.r, self.speed, self.sway = spec
        rnd = random.Random(f"{theme}{seed}")
        # posições como FRAÇÃO da tela: o efeito acompanha janelas de largura diferente
        self.items = [(rnd.uniform(0, 1), rnd.uniform(0.15, 0.85), rnd.uniform(0.5, 1.4),
                       rnd.uniform(0, math.tau), rnd.uniform(0.4, 1.0)) for _ in range(n)]

    def draw(self, surf: pygame.Surface, t: float, scroll: float = 0.0) -> None:
        w, h = surf.get_size()
        for fx, fy, spd, ph, depth in self.items:
            x = (fx * w + t * self.speed * spd - scroll * 0.25 * depth) % w
            y = fy * h + math.sin(t * 0.8 * spd + ph) * self.sway
            tw = 0.55 + 0.45 * math.sin(t * 2.2 * spd + ph)          # brilho que pulsa
            r = max(2, int(self.r * depth))
            g = _glow(self.color, r)
            if tw < 0.99:
                g = _glow(tuple(int(c * tw) for c in self.color), r)
            surf.blit(g, (x - r * 2, y - r * 2), special_flags=pygame.BLEND_RGB_ADD)
