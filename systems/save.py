"""Persistência: JSON em <USER_DIR>/saves, escrita atômica (tmp + replace) e backup.

Fica fora da pasta de instalação, então updates/reinstalações não apagam progresso."""
import json
import os
from pathlib import Path

from core import paths

SAVE_VERSION = 1


class SaveManager:
    def __init__(self, slot: str = "slot1") -> None:
        self.path: Path = paths.SAVE_DIR / f"{slot}.json"

    def exists(self) -> bool:
        return self.path.is_file()

    def load_raw(self) -> dict | None:
        for p in (self.path, self.path.with_suffix(".bak")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return self._migrate(data)
            except (OSError, ValueError):
                continue
        return None

    def save(self, profile) -> None:
        data = profile.to_dict()
        data["save_version"] = SAVE_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if self.path.exists():
            os.replace(self.path, self.path.with_suffix(".bak"))
        os.replace(tmp, self.path)

    def delete(self) -> None:
        for suf in (".json", ".bak"):
            self.path.with_suffix(suf).unlink(missing_ok=True)

    @staticmethod
    def _migrate(data: dict) -> dict:
        # Ponto único para migrar saves antigos quando o formato mudar.
        data.setdefault("save_version", SAVE_VERSION)
        return data
