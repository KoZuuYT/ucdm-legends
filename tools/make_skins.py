"""Gera os sprites de corpo inteiro (vista frontal, 16x32 px) a partir das skins de Minecraft em assets/mc.

Uso:  python tools/make_skins.py
Saída: assets/sprites/characters/skin_<id>.png  (pixel-art nativa; o jogo escala com vizinho mais próximo)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKIN_DIR = ROOT / "assets" / "mc" / "entity" / "player"
OUT = ROOT / "assets" / "sprites" / "characters"

# id -> modelo de braço (wide = 4 px, slim = 3 px)
SKINS = {"steve": "wide", "alex": "slim", "ari": "wide", "efe": "wide", "kai": "wide",
         "makena": "slim", "noor": "slim", "sunny": "slim", "zuri": "slim"}


def part(skin: pygame.Surface, x: int, y: int, w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.blit(skin, (0, 0), (x, y, w, h))
    return s


def build(skin: pygame.Surface, arm_w: int) -> pygame.Surface:
    out = pygame.Surface((16, 32), pygame.SRCALPHA)
    def put(x, y, base, over):
        out.blit(base, (x, y))
        out.blit(over, (x, y))
    # pernas (direita do personagem aparece à esquerda de quem vê)
    put(4, 20, part(skin, 4, 20, 4, 12), part(skin, 4, 36, 4, 12))
    put(8, 20, part(skin, 20, 52, 4, 12), part(skin, 4, 52, 4, 12))
    # corpo e cabeça
    put(4, 8, part(skin, 20, 20, 8, 12), part(skin, 20, 36, 8, 12))
    put(4, 0, part(skin, 8, 8, 8, 8), part(skin, 40, 8, 8, 8))
    # braços (modelo slim tem 3 px de largura)
    put(4 - arm_w, 8, part(skin, 44, 20, arm_w, 12), part(skin, 44, 36, arm_w, 12))
    put(12, 8, part(skin, 36, 52, arm_w, 12), part(skin, 52, 52, arm_w, 12))
    return out


def main() -> int:
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for sid, model in SKINS.items():
        src = SKIN_DIR / model / f"{sid}.png"
        if not src.exists():
            src = SKIN_DIR / "wide" / f"{sid}.png"
        if not src.exists():
            print(f"[skins] ausente: {src}")
            continue
        skin = pygame.image.load(str(src)).convert_alpha()
        if skin.get_size() != (64, 64):
            print(f"[skins] tamanho inesperado em {sid}: {skin.get_size()}")
            continue
        pygame.image.save(build(skin, 3 if model == "slim" else 4), str(OUT / f"skin_{sid}.png"))
        made += 1
    print(f"[skins] {made} sprites gerados em {OUT}")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
