"""Resolução centralizada de caminhos.

Funciona tanto rodando do código-fonte (python main.py) quanto empacotado
com PyInstaller (onedir). Dados do jogador ficam FORA da pasta de instalação,
para que atualizações nunca apaguem saves ou mods.
"""
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# Pasta raiz da instalação (onde ficam assets/, version.json, executável).
if FROZEN:
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = ASSETS_DIR / "data"
VERSION_FILE = BASE_DIR / "version.json"


def _user_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return root / "UCDM"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "UCDM"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ucdm"


USER_DIR = Path(os.environ.get("UCDM_USER_DIR", _user_dir()))
SAVE_DIR = USER_DIR / "saves"
MODS_DIR = USER_DIR / "mods"          # mods/<qualquer>/assets/... sobrepõe assets oficiais
UPDATE_DIR = USER_DIR / "update"      # downloads e staging do auto-update


def ensure_user_dirs() -> None:
    for d in (USER_DIR, SAVE_DIR, MODS_DIR, UPDATE_DIR):
        d.mkdir(parents=True, exist_ok=True)
