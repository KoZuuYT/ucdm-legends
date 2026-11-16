"""Persistência: JSON em <USER_DIR>/saves, escrita atômica (tmp + replace) e backup.

Fica fora da pasta de instalação, então updates/reinstalações não apagam progresso.
Três slots (slot1..slot3). O slot1 é o save das versões antigas, que continua valendo.
"""
import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from core import paths

SAVE_VERSION = 2
EXPORT_EXT = ".ucdmsave"


class SaveManager:
    def __init__(self, slot: str = "slot1", on_saved: Callable[[], None] | None = None) -> None:
        self.slot = slot
        self.path: Path = paths.SAVE_DIR / f"{slot}.json"
        self.on_saved = on_saved

    # --- leitura ------------------------------------------------------------------------
    def exists(self) -> bool:
        return self.path.is_file() or self.path.with_suffix(".bak").is_file()

    def load_raw(self) -> dict | None:
        """Lê o save; se o principal estiver corrompido, usa o .bak (flag `_from_backup`)."""
        for i, p in enumerate((self.path, self.path.with_suffix(".bak"))):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                if int(data.get("save_version", 1)) < SAVE_VERSION:
                    self._backup_old_version(p, int(data.get("save_version", 1)))
                data = self._migrate(data)
                data["_from_backup"] = i == 1
                return data
            except (OSError, ValueError):
                continue
        return None

    def _backup_old_version(self, src: Path, version: int) -> None:
        """Cópia de segurança antes de migrar um save de formato antigo (uma por versão)."""
        dst = self.path.with_name(f"{self.slot}.v{version}.bak")
        if not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                print(f"[save] backup de migração falhou: {e}")

    def summary(self) -> dict | None:
        """Resumo para o seletor de saves (sem montar o Profile). None = slot vazio."""
        data = self.load_raw()
        if data is None:
            return None
        stats = data.get("stats", {})
        total = sum(int(s.get("level", 1)) for s in stats.values()) - 3 if stats else 1
        try:
            mtime = max(p.stat().st_mtime for p in (self.path, self.path.with_suffix(".bak")) if p.exists())
        except ValueError:
            mtime = 0.0
        return {"slot": self.slot, "name": data.get("name", ""), "character": data.get("character", "steve"),
                "level": max(1, total), "wins": int(data.get("wins", 0)), "arena_stage": int(data.get("arena_stage", 0)),
                "gold": int(data.get("gold", 0)), "playtime": float(data.get("playtime", 0.0)), "mtime": mtime,
                "from_backup": bool(data.get("_from_backup"))}

    # --- escrita ------------------------------------------------------------------------
    def save(self, profile) -> None:
        self.write_dict(profile.to_dict())
        if self.on_saved:
            self.on_saved()

    def write_dict(self, data: dict) -> None:
        data = {k: v for k, v in data.items() if not k.startswith("_")}
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

    def copy_to(self, other: "SaveManager") -> bool:
        data = self.load_raw()
        if data is None:
            return False
        other.write_dict(data)
        return True

    # --- exportar / importar ------------------------------------------------------------
    def export(self) -> Path | None:
        """Grava <USER_DIR>/exports/<slot>-AAAAMMDD-HHMM.ucdmsave (JSON com save_version)."""
        data = self.load_raw()
        if data is None:
            return None
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        paths.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = paths.EXPORT_DIR / f"{self.slot}-{time.strftime('%Y%m%d-%H%M%S')}{EXPORT_EXT}"
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out

    def import_file(self, file: Path) -> bool:
        """Importa um .ucdmsave para este slot. Rejeita arquivos que não parecem um save."""
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict) or "stats" not in data or "character" not in data:
            return False
        self._backup_existing()
        self.write_dict(self._migrate(data))
        return True

    def _backup_existing(self) -> None:
        if self.path.is_file():
            try:
                shutil.copy2(self.path, self.path.with_name(f"{self.slot}.antes-importar.bak"))
            except OSError:
                pass

    @staticmethod
    def list_exports() -> list[Path]:
        if not paths.EXPORT_DIR.is_dir():
            return []
        return sorted(paths.EXPORT_DIR.glob(f"*{EXPORT_EXT}"), key=lambda p: p.stat().st_mtime, reverse=True)

    @staticmethod
    def _migrate(data: dict) -> dict:
        # Ponto único para migrar saves antigos quando o formato mudar.
        # v1 -> v2: campos novos (playtime, name, counters, seen_help) têm padrão no Profile.from_dict.
        data["save_version"] = SAVE_VERSION
        return data
