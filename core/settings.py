"""Preferências do jogador: lê/escreve %APPDATA%/UCDM/settings.json (mesclado sobre game.json).

Escrita parcial e atômica: só as chaves alteradas entram no arquivo, então "restaurar padrão"
é apenas remover a chave. O instalador escreve o mesmo arquivo (core/config.py faz o merge).
"""
import json
import os

from core import config, paths


def read() -> dict:
    try:
        data = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    paths.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, paths.SETTINGS_FILE)
    config.clear_cache()


def set_value(path: str, value) -> None:
    """set_value("audio.sfx_volume", 0.5) grava só essa chave."""
    data = read()
    node = data
    keys = path.split(".")
    for k in keys[:-1]:
        if not isinstance(node.get(k), dict):
            node[k] = {}
        node = node[k]
    node[keys[-1]] = value
    _write(data)


def remove(path: str) -> None:
    """Remove a chave (volta ao padrão do game.json) e limpa dicionários que ficaram vazios."""
    data = read()
    keys = path.split(".")
    chain = [data]
    node = data
    for k in keys[:-1]:
        node = node.get(k)
        if not isinstance(node, dict):
            return
        chain.append(node)
    if keys[-1] not in node:
        return
    del node[keys[-1]]
    for parent, k in zip(reversed(chain[:-1]), reversed(keys[:-1])):
        if not parent[k]:
            del parent[k]
    _write(data)


def get(path: str, default=None):
    """Valor efetivo (settings sobre game.json)."""
    node = config.load("game", reload=True)
    for k in path.split("."):
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node
