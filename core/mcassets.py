"""Acesso aos assets de Minecraft (assets/mc): sprites em pixel-art, 9-slice e animações.

- Escala sempre **inteira com vizinho mais próximo** (pixel-art nítida).
- 9-slice lido dos arquivos `.mcmeta` (botões, painéis, barras).
- Tudo em cache; se um arquivo faltar, devolve None e quem chama cai para o visual padrão.
"""
import json
from pathlib import Path

import pygame

from core import paths

ROOT: Path = paths.ASSETS_DIR / "mc"
GUI = "gui/sprites/"

_img: dict[str, pygame.Surface | None] = {}
_scaled: dict[tuple, pygame.Surface] = {}
_nine: dict[tuple, pygame.Surface] = {}
_meta: dict[str, dict] = {}


def available() -> bool:
    return (ROOT / "gui").is_dir()


def load(rel: str) -> pygame.Surface | None:
    """Carrega assets/mc/<rel> (com alpha). None se não existir."""
    if rel in _img:
        return _img[rel]
    f = ROOT / rel
    surf = None
    if f.is_file():
        try:
            surf = pygame.image.load(str(f))
            surf = surf.convert_alpha() if pygame.display.get_surface() else surf
        except pygame.error:
            surf = None
    _img[rel] = surf
    return surf


def sprite(rel: str, k: int = 1) -> pygame.Surface | None:
    """Sprite escalado por um fator inteiro k."""
    base = load(rel)
    if base is None:
        return None
    if k == 1:
        return base
    key = (rel, k)
    s = _scaled.get(key)
    if s is None:
        if len(_scaled) > 400:
            _scaled.clear()
        s = _scaled[key] = pygame.transform.scale(base, (base.get_width() * k, base.get_height() * k))
    return s


def sprite_h(rel: str, height: int) -> pygame.Surface | None:
    """Sprite com altura aproximada `height` (fator inteiro mais próximo, no mínimo 1)."""
    base = load(rel)
    if base is None:
        return None
    return sprite(rel, max(1, round(height / base.get_height())))


def frames(prefix: str, count: int) -> list[pygame.Surface]:
    """Quadros `<prefix>_0.png .. <prefix>_{count-1}.png` (ex.: particle/sweep). Ignora os que faltam."""
    out = []
    for i in range(count):
        s = load(f"{prefix}_{i}.png")
        if s is not None:
            out.append(s)
    return out


def _border(rel: str) -> tuple[int, int, int, int]:
    """(esq, cima, dir, baixo) do 9-slice a partir do .mcmeta; (0,0,0,0) se não houver."""
    m = _meta.get(rel)
    if m is None:
        m = {}
        f = ROOT / (rel + ".mcmeta")
        if f.is_file():
            try:
                m = json.loads(f.read_text(encoding="utf-8")).get("gui", {}).get("scaling", {})
            except (OSError, ValueError):
                m = {}
        _meta[rel] = m
    b = m.get("border") if m.get("type") == "nine_slice" else None
    if b is None:
        return (0, 0, 0, 0)
    if isinstance(b, int):
        return (b, b, b, b)
    return (b.get("left", 0), b.get("top", 0), b.get("right", 0), b.get("bottom", 0))


def nine(rel: str, size: tuple[int, int], k: int = 2) -> pygame.Surface | None:
    """Desenha um sprite 9-slice no tamanho `size` (px da tela) com bordas ampliadas k vezes."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    key = (rel, w, h, k)
    s = _nine.get(key)
    if s is not None:
        return s
    src = load(rel)
    if src is None:
        return None
    l, t, r, b = _border(rel)
    sw, sh = src.get_size()
    if not (l or t or r or b):
        out = pygame.transform.scale(src, (w, h))
    else:
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        L, T, R, B = l * k, t * k, r * k, b * k
        if L + R > w or T + B > h:                 # pequeno demais: reduz o fator
            k = max(1, min((w // max(1, l + r)) or 1, (h // max(1, t + b)) or 1))
            L, T, R, B = l * k, t * k, r * k, b * k
        xs = [(0, l, 0, L), (l, sw - r, L, w - R), (sw - r, sw, w - R, w)]
        ys = [(0, t, 0, T), (t, sh - b, T, h - B), (sh - b, sh, h - B, h)]
        for sx0, sx1, dx0, dx1 in xs:
            for sy0, sy1, dy0, dy1 in ys:
                if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                    continue
                piece = src.subsurface((sx0, sy0, sx1 - sx0, sy1 - sy0))
                out.blit(pygame.transform.scale(piece, (dx1 - dx0, dy1 - dy0)), (dx0, dy0))
    if len(_nine) > 300:
        _nine.clear()
    _nine[key] = out
    return out


def clear_cache() -> None:
    _img.clear()
    _scaled.clear()
    _nine.clear()
    _meta.clear()


_stretch: dict[tuple, pygame.Surface] = {}


def stretch(rel: str, size: tuple[int, int]) -> pygame.Surface | None:
    """Estica um sprite (sem suavizar) para `size`; usado em barras planas (boss bar, XP)."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    key = (rel, w, h)
    s = _stretch.get(key)
    if s is None:
        src = load(rel)
        if src is None:
            return None
        if len(_stretch) > 200:
            _stretch.clear()
        s = _stretch[key] = pygame.transform.scale(src, (w, h))
    return s


_tinted: dict[tuple, pygame.Surface] = {}


def tinted(rel: str, k: int, color: tuple) -> pygame.Surface | None:
    """Sprite (geralmente branco/cinza, como as partículas do Minecraft) multiplicado por uma cor. Em cache."""
    base = sprite(rel, k)
    if base is None:
        return None
    key = (rel, k, tuple(color[:3]))
    s = _tinted.get(key)
    if s is None:
        if len(_tinted) > 300:
            _tinted.clear()
        s = _tinted[key] = base.copy()
        s.fill(tuple(color[:3]), special_flags=pygame.BLEND_RGB_MULT)
    return s
