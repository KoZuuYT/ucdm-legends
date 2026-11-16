"""Idiomas. O texto-fonte do jogo é PT-BR; outros idiomas são tabelas "português -> tradução".

assets/data/lang/<código>.json  ->  {"name": "English", "strings": {"Opções": "Options", "Luta {}/{}": "Fight {}/{}"}}

`tr(texto)` é chamado por ui.text(), então toda UI desenhada por ela é traduzida sem mexer nas cenas.
Chaves com "{}" funcionam como padrão (os trechos variáveis são reaproveitados na tradução, em ordem).
Texto sem tradução cai no original: nunca quebra, só aparece em português. Mods podem adicionar idiomas
em <USER_DIR>/mods/<mod>/data/lang/.
"""
import json
import re
from pathlib import Path

from core import paths

DEFAULT = "pt-BR"
_lang = DEFAULT
_exact: dict[str, str] = {}
_patterns: list[tuple[re.Pattern, str]] = []
_cache: dict[str, str] = {}


def _dirs() -> list[Path]:
    out = [paths.DATA_DIR / "lang"]
    if paths.MODS_DIR.is_dir():
        out += [m / "data" / "lang" for m in sorted(paths.MODS_DIR.iterdir()) if m.is_dir()]
    return out


def available() -> list[tuple[str, str]]:
    """[(código, nome)] — PT-BR sempre primeiro."""
    found: dict[str, str] = {DEFAULT: "Português (BR)"}
    for d in _dirs():
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                try:
                    found[f.stem] = json.loads(f.read_text(encoding="utf-8")).get("name", f.stem)
                except (OSError, ValueError):
                    continue
    return list(found.items())


def set_language(code: str) -> str:
    """Carrega o idioma; código desconhecido volta para PT-BR. Devolve o código efetivo."""
    global _lang
    _exact.clear()
    _patterns.clear()
    _cache.clear()
    _lang = DEFAULT
    if code == DEFAULT:
        return _lang
    strings: dict[str, str] = {}
    for d in _dirs():
        f = d / f"{code}.json"
        if f.is_file():
            try:
                strings.update(json.loads(f.read_text(encoding="utf-8")).get("strings", {}))
            except (OSError, ValueError) as e:
                print(f"[i18n] {f}: {e}")
    if not strings:
        return _lang
    _lang = code
    pats = []
    for k, v in strings.items():
        if "{}" in k:
            rx = "^" + "(.+?)".join(re.escape(p) for p in k.split("{}")) + "$"
            pats.append((len(k.replace("{}", "")), re.compile(rx), v))
        else:
            _exact[k] = v
    # padrões com mais texto fixo primeiro: "Arma nv {}" ganha de "{} nv {}"
    _patterns.extend((rx, v) for _, rx, v in sorted(pats, key=lambda p: -p[0]))
    return _lang


def language() -> str:
    return _lang


def tr(s):
    if _lang == DEFAULT or not isinstance(s, str) or not s:
        return s
    hit = _exact.get(s)
    if hit is not None:
        return hit
    cached = _cache.get(s)
    if cached is not None:
        return cached
    for rx, out in _patterns:
        m = rx.match(s)
        if m:
            try:
                res = out.format(*(tr(g) for g in m.groups()))
            except (IndexError, KeyError, ValueError):
                res = s
            if len(_cache) < 512:      # textos com números mudam sempre: limita o cache
                _cache[s] = res
            return res
    return s
