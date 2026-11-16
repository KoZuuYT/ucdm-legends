"""Ícones de atributo desenhados por código (sem arquivos), com forma própria para não depender só da cor."""
import pygame

_cache: dict[tuple, pygame.Surface] = {}
_DARK = (15, 16, 24)


def _poly(s, color, pts, k):
    pts = [(x * k, y * k) for x, y in pts]
    pygame.draw.polygon(s, color, pts)
    pygame.draw.polygon(s, _DARK, pts, max(1, round(k / 12)))


def stat_icon(stat: str, size: int, color) -> pygame.Surface:
    """strength = espada, defense = escudo, agility = raio, focus = mira. Cacheado por (stat, size, cor)."""
    key = (stat, size, tuple(color))
    img = _cache.get(key)
    if img is not None:
        return img
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 24
    c = tuple(color)
    if stat == "strength":       # espada na diagonal
        _poly(s, c, [(19, 2), (22, 5), (10, 17), (7, 14)], k)
        _poly(s, (200, 200, 210), [(4, 13), (11, 20), (9, 22), (2, 15)], k)
        pygame.draw.line(s, _DARK, (3 * k, 21 * k), (7 * k, 17 * k), max(2, round(2.4 * k)))
    elif stat == "defense":      # escudo
        _poly(s, c, [(12, 2), (21, 5), (20, 14), (12, 22), (4, 14), (3, 5)], k)
        pygame.draw.line(s, _DARK, (12 * k, 4 * k), (12 * k, 19 * k), max(1, round(k)))
    elif stat == "agility":      # raio
        _poly(s, c, [(14, 1), (5, 13), (11, 13), (9, 23), (19, 10), (13, 10)], k)
    elif stat == "focus":        # mira
        pygame.draw.circle(s, _DARK, (12 * k, 12 * k), 10 * k, max(3, round(3.4 * k)))
        pygame.draw.circle(s, c, (12 * k, 12 * k), 10 * k, max(2, round(2 * k)))
        for p0, p1 in (((12, 0), (12, 7)), ((12, 17), (12, 24)), ((0, 12), (7, 12)), ((17, 12), (24, 12))):
            pygame.draw.line(s, c, (p0[0] * k, p0[1] * k), (p1[0] * k, p1[1] * k), max(2, round(2 * k)))
        pygame.draw.circle(s, c, (12 * k, 12 * k), max(2, round(2 * k)))
    else:
        pygame.draw.circle(s, c, (size // 2, size // 2), size // 3)
    _cache[key] = s
    return s
