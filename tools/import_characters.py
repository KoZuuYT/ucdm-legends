"""Importa artes de personagens para o jogo.

Uso:
    python tools/import_characters.py [pasta_origem] [--max-height 320]

* Converte cada PNG para assets/sprites/characters/<id>.png (redimensionado,
  economizando RAM/disco — as artes originais chegam a 600px+).
* Gera/atualiza assets/data/characters.json. Entradas já existentes NÃO são
  sobrescritas, então nomes/atributos editados à mão são preservados.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "sprites" / "characters"
ROSTER = ROOT / "assets" / "data" / "characters.json"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "personagem"


def pretty(name: str) -> str:
    return name[:1].upper() + name[1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default=str(ROOT / "UCDM"))
    ap.add_argument("--max-height", type=int, default=320)
    args = ap.parse_args()

    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))

    src = Path(args.source)
    if not src.is_dir():
        print(f"Pasta não encontrada: {src}")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    roster = json.loads(ROSTER.read_text(encoding="utf-8")) if ROSTER.exists() else {"characters": []}
    known = {c["id"]: c for c in roster["characters"]}

    added = 0
    for f in sorted(src.iterdir(), key=lambda p: p.name.lower()):
        if f.suffix.lower() != ".png":
            continue
        cid = slugify(f.stem)
        if cid in known and known[cid].get("source") != f.name:
            n = 2
            while f"{cid}_{n}" in known:
                n += 1
            cid = f"{cid}_{n}"
        img = pygame.image.load(str(f)).convert_alpha()
        # recorta transparência sobrando ao redor
        bbox = img.get_bounding_rect()
        if bbox.width and bbox.height:
            img = img.subsurface(bbox).copy()
        w, h = img.get_size()
        if h > args.max_height:
            img = pygame.transform.smoothscale(img, (max(1, round(w * args.max_height / h)), args.max_height))
        pygame.image.save(img, str(OUT_DIR / f"{cid}.png"))
        if cid not in known:
            entry = {"id": cid, "name": pretty(f.stem), "sprite": f"sprites/characters/{cid}.png",
                     "faces": -1, "source": f.name}
            roster["characters"].append(entry)
            known[cid] = entry
            added += 1

    roster["characters"].sort(key=lambda c: c["name"].lower())
    ROSTER.parent.mkdir(parents=True, exist_ok=True)
    ROSTER.write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(roster['characters'])} personagens no elenco ({added} novos) -> {ROSTER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
