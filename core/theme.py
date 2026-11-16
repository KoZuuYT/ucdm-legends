"""Tema da interface (Opções -> Vídeo -> Tema). Dados em assets/data/theme.json.

`classic` = visual "Torneio" desenhado em código; `mc` = sprites de Minecraft (assets/mc).
Os widgets de core/ui.py consultam `theme.mc()` e delegam o desenho para core/mcui.py."""
from core import config, mcassets

name = "torneio"


def themes() -> dict:
    return config.load("theme")["themes"]


def set_theme(new: str) -> None:
    global name
    name = new if new in themes() else config.load("theme").get("default", "torneio")


def info() -> dict:
    return themes().get(name, {})


def mc() -> bool:
    """True se o tema atual usa os sprites de Minecraft e eles existem."""
    return info().get("style") == "mc" and mcassets.available()


def color(token: str, default=(255, 255, 255)) -> tuple:
    return tuple(info().get(token, default))
