"""Fonte bitmap do Minecraft (assets/mc/font/ascii.png) com a mesma interface mínima de pygame.font.Font.

Acentos do português (á à â ã ä ç é ê í ó ô õ ú ü...) são desenhados à mão por cima da letra base: o atlas
ascii.png só tem ASCII. A fonte tem 11 linhas de altura (2 acima para os acentos, 1 abaixo para a cedilha)."""
import unicodedata

import pygame

from core import mcassets

ROWS_TOP, ROWS_GLYPH, ROWS_BOTTOM = 2, 8, 1
CELL = 8
_atlas: pygame.Surface | None = None
_glyphs: dict[str, pygame.Surface] = {}
_text_cache: dict[tuple, pygame.Surface] = {}


def available() -> bool:
    return mcassets.sprite("font/ascii.png", 1) is not None


def _atlas_surface() -> pygame.Surface | None:
    global _atlas
    if _atlas is None:
        _atlas = mcassets.load("font/ascii.png")
    return _atlas


def _base_glyph(ch: str) -> pygame.Surface | None:
    """Glifo ASCII em branco (largura = coluna mais à direita usada, +0)."""
    code = ord(ch)
    atlas = _atlas_surface()
    if atlas is None or not 32 <= code < 128:
        return None
    cx, cy = (code % 16) * CELL, (code // 16) * CELL
    cell = atlas.subsurface((cx, cy, CELL, CELL))
    width = 0
    for x in range(CELL):
        if any(cell.get_at((x, y)).a > 0 for y in range(CELL)):
            width = x + 1
    if ch == " " or width == 0:
        width = 3
    out = pygame.Surface((width, ROWS_TOP + ROWS_GLYPH + ROWS_BOTTOM), pygame.SRCALPHA)
    out.blit(cell, (0, ROWS_TOP), (0, 0, width, CELL))
    return out


_MARKS = {
    "\u0301": lambda c: [(c + 1, 0), (c, 1)],                    # agudo
    "\u0300": lambda c: [(c - 1, 0), (c, 1)],                    # grave
    "\u0302": lambda c: [(c, 0), (c - 1, 1), (c + 1, 1)],        # circunflexo
    "\u0303": lambda c: [(c - 1, 1), (c, 0), (c + 1, 0)],        # til
    "\u0308": lambda c: [(c - 1, 1), (c + 1, 1)],                # trema
}


_SPECIAL = {                                   # símbolos que não existem no atlas ASCII
    "·": (2, [(0, 4), (1, 4)]), "•": (3, [(0, 3), (1, 3), (2, 3), (0, 4), (1, 4), (2, 4), (1, 2), (1, 5)]),
    "✓": (6, [(0, 5), (1, 6), (2, 7), (3, 6), (4, 5), (5, 4), (6, 3)]), "→": (6, [(x, 4) for x in range(6)] + [(4, 3), (4, 5), (3, 2), (3, 6)]),
    "—": (6, [(x, 4) for x in range(6)]), "–": (5, [(x, 4) for x in range(5)]),
}


def glyph(ch: str) -> pygame.Surface:
    g = _glyphs.get(ch)
    if g is not None:
        return g
    if ch in _SPECIAL:
        w, px = _SPECIAL[ch]
        s = pygame.Surface((w + 1, ROWS_TOP + ROWS_GLYPH + ROWS_BOTTOM), pygame.SRCALPHA)
        for x, y in px:
            if x <= w:
                s.set_at((x, y + ROWS_TOP - 1), (255, 255, 255, 255))
        _glyphs[ch] = s
        return s
    base = unicodedata.normalize("NFD", ch)
    surf = _base_glyph(base[0]) or _base_glyph("?")
    if surf is None:
        surf = pygame.Surface((5, ROWS_TOP + ROWS_GLYPH + ROWS_BOTTOM), pygame.SRCALPHA)
    surf = surf.copy()
    c = max(0, surf.get_width() // 2 - (1 if surf.get_width() % 2 == 0 else 0))
    for m in base[1:]:
        if m in _MARKS:
            for x, y in _MARKS[m](c):
                if 0 <= x < surf.get_width():
                    surf.set_at((x, y), (255, 255, 255, 255))
        elif m == "\u0327":                                      # cedilha
            surf.set_at((c, surf.get_height() - 1), (255, 255, 255, 255))
    _glyphs[ch] = surf
    return surf


class BitmapFont:
    """Subconjunto de pygame.font.Font usado pelo jogo: render, size, get_height, get_linesize, set_bold."""

    def __init__(self, scale: int) -> None:
        self.scale = max(1, int(scale))

    def set_bold(self, _b: bool) -> None:
        pass

    def get_bold(self) -> bool:
        return False

    def get_height(self) -> int:
        return (ROWS_TOP + ROWS_GLYPH + ROWS_BOTTOM) * self.scale

    get_linesize = get_height

    def size(self, text: str) -> tuple[int, int]:
        text = text.replace("…", "...")
        w = sum(glyph(ch).get_width() + 1 for ch in text)
        return max(0, w - 1) * self.scale if text else 0, self.get_height()

    def render(self, text: str, antialias: bool = True, color=(255, 255, 255), background=None) -> pygame.Surface:
        text = text.replace("…", "...")
        key = (text, tuple(color)[:3], self.scale, background)
        hit = _text_cache.get(key)
        if hit is not None:
            return hit
        w, h = self.size(text)
        out = pygame.Surface((max(1, w // self.scale), ROWS_TOP + ROWS_GLYPH + ROWS_BOTTOM), pygame.SRCALPHA)
        x = 0
        for ch in text:
            g = glyph(ch)
            out.blit(g, (x, 0))
            x += g.get_width() + 1
        out.fill((*tuple(color)[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)
        if self.scale > 1:
            out = pygame.transform.scale(out, (out.get_width() * self.scale, out.get_height() * self.scale))
        if background is not None:
            bg = pygame.Surface(out.get_size())
            bg.fill(background)
            bg.blit(out, (0, 0))
            out = bg
        if len(_text_cache) > 3000:
            _text_cache.clear()
        _text_cache[key] = out
        return out


def for_size(size: int) -> BitmapFont:
    """Escala inteira que mais se aproxima do tamanho pedido em pixels de uma fonte comum."""
    return BitmapFont(max(1, round(size / 12)))
