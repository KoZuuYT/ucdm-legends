"""Verificação de integridade da instalação: compara os arquivos com o manifest.json do Release.

Só olha arquivos listados no manifest (saves e mods ficam fora da pasta de instalação). Manifests antigos
(sem "hashes") só permitem checar se os arquivos existem. Roda numa thread e é observável pela UI.
"""
import json
import threading
from pathlib import Path

from network import release_tools as rt


def verify(install_dir: Path, progress=None) -> dict:
    """Devolve {"state": "ok"|"problems"|"nomanifest", "total", "missing": [...], "modified": [...], "hashed": bool}."""
    try:
        man = json.loads((install_dir / rt.MANIFEST).read_text(encoding="utf-8"))
        files: list[str] = man["files"]
    except (OSError, ValueError, KeyError):
        return {"state": "nomanifest", "total": 0, "missing": [], "modified": [], "hashed": False}
    hashes: dict[str, str] = man.get("hashes", {})
    missing, modified = [], []
    for i, rel in enumerate(files):
        p = install_dir / rel
        if not p.is_file():
            missing.append(rel)
        elif hashes.get(rel) and rt.sha256_file(p) != hashes[rel]:
            modified.append(rel)
        if progress:
            progress((i + 1) / max(1, len(files)))
    state = "problems" if (missing or modified) else "ok"
    return {"state": state, "total": len(files), "missing": missing, "modified": modified, "hashed": bool(hashes)}


class IntegrityTask:
    def __init__(self, install_dir: Path) -> None:
        self.install_dir = install_dir
        self.progress = 0.0
        self.result: dict | None = None
        self.error = ""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:          # enter() pode ser chamado de novo se a cena for reempilhada
            self._started = True
            self._thread.start()

    def _run(self) -> None:
        try:
            self.result = verify(self.install_dir, lambda k: setattr(self, "progress", k))
        except Exception as e:  # noqa: BLE001 — a UI só precisa saber que falhou
            self.error = f"{type(e).__name__}: {e}"
