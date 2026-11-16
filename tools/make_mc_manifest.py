"""Gera assets/mc/manifest.json (sha256 de cada arquivo de Minecraft). Rode depois de mudar assets/mc.
O teste tests/test_extras.py confere que o manifesto bate com os arquivos."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "assets" / "mc"


def build() -> dict:
    files = {}
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            files[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"count": len(files), "files": files}


if __name__ == "__main__":
    m = build()
    (ROOT / "manifest.json").write_text(json.dumps(m, indent=0), encoding="utf-8")
    print(f"{m['count']} arquivos")
    sys.exit(0)
