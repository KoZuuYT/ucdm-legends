"""Carregamento de configuração data-driven (JSON, YAML opcional).

Todo balanceamento (atributos, inimigos, mini-games) vem de assets/data/.
Mods podem sobrescrever qualquer chave: o arquivo
<USER_DIR>/mods/<nome_do_mod>/data/<arquivo>.json é mesclado (deep merge)
por cima do oficial, em ordem alfabética de nome de mod.
Por último, <USER_DIR>/settings.json (preferências do jogador: tela, áudio,
updates) é mesclado por cima de game.json.
"""
import json
from pathlib import Path
from typing import Any

from core import paths

try:  # YAML é opcional; o jogo funciona só com JSON.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

_cache: dict[str, Any] = {}


def _read(path: Path) -> Any:
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError(f"PyYAML não instalado; não é possível ler {path}")
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: Any, over: Any) -> Any:
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(out[k], v) if k in out else v
        return out
    return over


def _find(directory: Path, name: str) -> Path | None:
    for ext in (".json", ".yaml", ".yml"):
        p = directory / f"{name}{ext}"
        if p.is_file():
            return p
    return None


def load(name: str, *, reload: bool = False) -> Any:
    """Carrega assets/data/<name>.(json|yaml) + overrides de mods."""
    if name in _cache and not reload:
        return _cache[name]
    base_path = _find(paths.DATA_DIR, name)
    if base_path is None:
        raise FileNotFoundError(f"Config '{name}' não encontrada em {paths.DATA_DIR}")
    data = _read(base_path)
    if paths.MODS_DIR.is_dir():
        for mod in sorted(p for p in paths.MODS_DIR.iterdir() if p.is_dir()):
            over = _find(mod / "data", name)
            if over:
                data = deep_merge(data, _read(over))
    if name == "game" and paths.SETTINGS_FILE.is_file():
        try:
            data = deep_merge(data, _read(paths.SETTINGS_FILE))
        except (OSError, ValueError) as e:   # settings corrompido não pode impedir o jogo de abrir
            print(f"[config] settings.json ignorado: {e}")
    _cache[name] = data
    return data


def clear_cache() -> None:
    _cache.clear()
