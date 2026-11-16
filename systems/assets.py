"""AssetManager: carregamento preguiçoso, cache, LRU para versões escaladas
e suporte a mods (pastas externas sobrepõem assets oficiais).

Ordem de busca de "sprites/characters/kozu.png":
  1. <USER_DIR>/mods/<mod>/assets/sprites/characters/kozu.png  (z→a)
  2. <instalação>/assets/sprites/characters/kozu.png
Se nada existir, devolve um placeholder visível em vez de quebrar o jogo.
"""
from collections import OrderedDict
from pathlib import Path

import pygame

from core import paths

PIXEL_PREFIXES = ("sprites/characters/skin_", "mc/")      # pixel-art: escala inteira (vizinho mais próximo)


class AssetManager:
    def __init__(self, scaled_cache_bytes: int = 96 * 1024 * 1024) -> None:
        self._images: dict[str, pygame.Surface] = {}
        self._scaled: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self._scaled_bytes = 0
        self._scaled_limit = scaled_cache_bytes
        self._fonts: dict[tuple, pygame.font.Font] = {}
        self._sounds: dict[str, "pygame.mixer.Sound | None"] = {}
        self._missing: set[str] = set()
        self.font_scale = 1.0

    # --- resolução de caminhos --------------------------------------------------------
    def resolve(self, rel: str) -> Path | None:
        rel = rel.replace("\\", "/").lstrip("/")
        if ".." in Path(rel).parts:
            return None
        if paths.MODS_DIR.is_dir():
            for mod in sorted((p for p in paths.MODS_DIR.iterdir() if p.is_dir()), reverse=True):
                p = mod / "assets" / rel
                if p.is_file():
                    return p
        p = paths.ASSETS_DIR / rel
        return p if p.is_file() else None

    def list_dir(self, rel: str, suffixes=(".png",)) -> list[str]:
        """Lista arquivos (relativos a assets/) unindo oficiais + mods."""
        found: dict[str, None] = {}
        roots = [paths.ASSETS_DIR]
        if paths.MODS_DIR.is_dir():
            roots += [m / "assets" for m in sorted(paths.MODS_DIR.iterdir()) if m.is_dir()]
        for root in roots:
            d = root / rel
            if d.is_dir():
                for f in sorted(d.iterdir()):
                    if f.suffix.lower() in suffixes:
                        found[f"{rel}/{f.name}"] = None
        return list(found)

    # --- imagens -----------------------------------------------------------------------
    def image(self, rel: str) -> pygame.Surface:
        surf = self._images.get(rel)
        if surf is not None:
            return surf
        path = self.resolve(rel)
        if path is None:
            if rel not in self._missing:
                print(f"[assets] ausente: {rel}")
                self._missing.add(rel)
            surf = self._placeholder()
        else:
            surf = pygame.image.load(str(path))
            surf = surf.convert_alpha() if pygame.display.get_surface() else surf
        self._images[rel] = surf
        return surf

    def image_h(self, rel: str, height: int, flip: bool = False) -> pygame.Surface:
        """Imagem escalada para uma altura (mantém proporção). Cache LRU limitado por bytes."""
        key = (rel, height, flip)
        surf = self._scaled.get(key)
        if surf is not None:
            self._scaled.move_to_end(key)
            return surf
        src = self.image(rel)
        w, h = src.get_size()
        if rel.startswith(PIXEL_PREFIXES) and h <= 128:         # pixel-art: escala inteira, sem suavizar
            k = max(1, round(height / h))
            height, width = h * k, w * k
            surf = pygame.transform.scale(src, (width, height))
        else:
            width = max(1, round(w * height / max(h, 1)))
            surf = pygame.transform.smoothscale(src, (width, height))
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        self._scaled[key] = surf
        self._scaled_bytes += width * height * 4
        while self._scaled_bytes > self._scaled_limit and len(self._scaled) > 1:
            _, old = self._scaled.popitem(last=False)
            ow, oh = old.get_size()
            self._scaled_bytes -= ow * oh * 4
        return surf

    def thumb_path(self, char: dict) -> str:
        """Miniatura do personagem (assets/sprites/thumbs/<id>.png) ou, se não existir, a arte inteira."""
        rel = f"sprites/thumbs/{char['id']}.png"
        return rel if self.resolve(rel) else char["sprite"]

    def unload(self, prefix: str) -> None:
        """Libera imagens originais (ex.: ao sair da tela de seleção de personagem)."""
        for k in [k for k in self._images if k.startswith(prefix)]:
            del self._images[k]

    @staticmethod
    def _placeholder() -> pygame.Surface:
        s = pygame.Surface((64, 64))
        for y in range(0, 64, 16):
            for x in range(0, 64, 16):
                s.fill((255, 0, 255) if (x + y) // 16 % 2 == 0 else (30, 30, 30), (x, y, 16, 16))
        return s

    # --- fontes / sons -----------------------------------------------------------------
    bitmap_enabled = True                       # Opções: "Fonte pixelada" (só vale no tema Minecraft)

    def bitmap_font(self) -> bool:
        from core import mcfont, theme
        return self.bitmap_enabled and theme.mc() and mcfont.available()

    def set_font_scale(self, scale: float) -> None:
        scale = max(0.8, min(1.4, float(scale)))
        if scale != self.font_scale:
            self.font_scale = scale
            self._fonts.clear()

    def font(self, size: int, name: str | None = None, bold: bool = True) -> pygame.font.Font:
        size = max(8, round(size * self.font_scale))
        if not name and self.bitmap_font():
            key = ("bitmap", size)
            f = self._fonts.get(key)
            if f is None:
                from core import mcfont
                f = self._fonts[key] = mcfont.for_size(size)
            return f
        key = (name, size, bold)
        f = self._fonts.get(key)
        if f is None:
            path = self.resolve(f"fonts/{name}") if name else None
            if path is None and not name:
                path = self.resolve("fonts/default.ttf")
            f = pygame.font.Font(str(path) if path else None, size)
            if path is None:
                f.set_bold(bold)
            self._fonts[key] = f
        return f

    def sound(self, rel: str):
        if rel in self._sounds:
            return self._sounds[rel]
        snd = None
        path = self.resolve(rel)
        if path and pygame.mixer.get_init():
            try:
                snd = pygame.mixer.Sound(str(path))
            except pygame.error as e:
                print(f"[assets] falha ao carregar som {rel}: {e}")
        self._sounds[rel] = snd
        return snd

    # --- diagnóstico ---------------------------------------------------------------------
    def stats(self) -> str:
        return f"{len(self._images)} orig / {len(self._scaled)} esc ({self._scaled_bytes // 1048576} MB)"

    def end_frame(self) -> None:
        pass
