"""Gera as miniaturas (thumbnails) dos personagens em assets/sprites/thumbs/<id>.png.

    python tools/make_thumbs.py [--size 160]

Cada miniatura é a arte do personagem encaixada num quadrado transparente. São usadas na seleção de
personagem e no seletor de saves: carregam rápido e ocupam pouca memória (as artes grandes só entram na luta).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sprites" / "thumbs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=160)
    args = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    roster = json.loads((ROOT / "assets" / "data" / "characters.json").read_text(encoding="utf-8"))["characters"]
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in roster:
        src = ROOT / "assets" / c["sprite"]
        if not src.is_file():
            continue
        img = pygame.image.load(str(src)).convert_alpha()
        w, h = img.get_size()
        k = min(args.size / w, args.size / h)
        img = pygame.transform.smoothscale(img, (max(1, round(w * k)), max(1, round(h * k))))
        thumb = pygame.Surface((args.size, args.size), pygame.SRCALPHA)
        thumb.blit(img, img.get_rect(midbottom=(args.size // 2, args.size)))
        pygame.image.save(thumb, str(OUT / f"{c['id']}.png"))
        n += 1
    total = sum(p.stat().st_size for p in OUT.glob("*.png"))
    print(f"OK: {n} miniaturas, {total / 1048576:.1f} MB em {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
