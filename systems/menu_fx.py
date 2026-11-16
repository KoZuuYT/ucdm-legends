"""Efeitos do menu principal: panorama giratório (tema Minecraft), título extrudado e frase "splash"."""
import math

import pygame

from core import mcassets as mc

_pano: dict[int, pygame.Surface | None] = {}


def panorama(height: int) -> pygame.Surface | None:
    """Faixa horizontal com as 4 faces laterais do panorama de Minecraft, na altura pedida (em cache)."""
    if height in _pano:
        return _pano[height]
    faces = [mc.load(f"gui/title/background/panorama_{i}.png") for i in range(4)]
    if any(f is None for f in faces):
        _pano[height] = None
        return None
    side = faces[0].get_width()
    strip = pygame.Surface((side * 4, side))
    for i, f in enumerate(faces):
        strip.blit(f, (i * side, 0))
    w = round(side * 4 * height / side)
    s = pygame.transform.smoothscale(strip, (w, height))
    shade = pygame.Surface(s.get_size())          # escurece um pouco para texto e botões lerem bem
    shade.fill((150, 150, 160))
    s.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    if len(_pano) > 3:
        _pano.clear()
    _pano[height] = s
    return s


def draw_panorama(surf: pygame.Surface, t: float, speed: float = 14.0) -> bool:
    W, H = surf.get_size()
    pano = panorama(H)
    if pano is None:
        return False
    off = int(t * speed) % pano.get_width()
    surf.blit(pano, (-off, 0))
    if off + W > pano.get_width():
        surf.blit(pano, (pano.get_width() - off, 0))
    return True


_title_cache: dict = {}


def extruded_title(font, msg: str, color=(214, 214, 214), depth: int = 7) -> pygame.Surface:
    """Título em bloco: face clara + lateral escura empilhada (lembra letras de pedra). Em cache."""
    key = (font.get_height(), msg, color, depth)
    hit = _title_cache.get(key)
    if hit is not None:
        return hit
    face = font.render(msg, True, color)
    w, h = face.get_size()
    out = pygame.Surface((w + depth + 8, h + depth + 8), pygame.SRCALPHA)
    dark = font.render(msg, True, (52, 52, 58))
    edge = font.render(msg, True, (18, 18, 22))
    for i in range(depth, 0, -1):
        out.blit(dark, (i + 2, i + 2))
    for dx, dy in ((0, 2), (4, 2), (2, 0), (2, 4)):
        out.blit(edge, (dx, dy))
    out.blit(face, (2, 2))
    hi = font.render(msg, True, (255, 255, 255))
    hi.set_alpha(70)
    out.blit(hi, (2, 1))
    if len(_title_cache) > 8:
        _title_cache.clear()
    _title_cache[key] = out
    return out


def splash(font, msg: str, t: float, reduce_motion: bool = False) -> pygame.Surface:
    """Texto amarelo inclinado que pulsa (a tradição do menu do Minecraft)."""
    body = font.render(msg, True, (255, 255, 60))
    shadow = font.render(msg, True, (62, 62, 14))
    img = pygame.Surface((body.get_width() + 3, body.get_height() + 3), pygame.SRCALPHA)
    img.blit(shadow, (3, 3))
    img.blit(body, (0, 0))
    k = 1.0 if reduce_motion else 1.0 + 0.07 * math.sin(t * 6)
    return pygame.transform.rotozoom(img, 18, k)
