"""Desenho de widgets no estilo Minecraft (botões 9-slice, painéis, corações, barras de chefe).

Cada função devolve False se faltar algum sprite, para o chamador usar o visual padrão."""
import pygame

from core import mcassets as mc
from core import theme

BTN = mc.GUI + "widget/button.png"
BTN_HI = mc.GUI + "widget/button_highlighted.png"
BTN_OFF = mc.GUI + "widget/button_disabled.png"
POPUP = mc.GUI + "popup/background.png"
HEART = mc.GUI + "hud/heart/"
HUD = mc.GUI + "hud/"
BOSS = mc.GUI + "boss_bar/"


def scale_for(height: int) -> int:
    return 2 if height < 56 else 3


def button(surf, rect: pygame.Rect, lit: bool, enabled: bool) -> bool:
    rel = BTN_OFF if not enabled else BTN_HI if lit else BTN
    img = mc.nine(rel, rect.size, scale_for(rect.h))
    if img is None:
        return False
    surf.blit(img, rect)
    return True


def label(surf, font, msg: str, center, lit: bool, enabled: bool) -> None:
    """Texto do botão: branco com sombra dura; amarelo claro ao destacar (como no jogo original)."""
    col = theme.color("text") if enabled and not lit else theme.color("text_hover") if enabled else theme.color("text_disabled")
    shadow = theme.color("shadow")
    body = font.render(msg, True, col)
    sh = font.render(msg, True, shadow)
    r = body.get_rect(center=center)
    d = 2 if font.get_height() < 40 else 3
    surf.blit(sh, r.move(d, d))
    surf.blit(body, r)


def panel(surf, rect: pygame.Rect) -> bool:
    img = mc.nine(POPUP, rect.size, 2)
    if img is None:
        return False
    surf.blit(img, rect)
    return True


def hearts(surf, x: int, y: int, frac: float, *, count: int = 10, k: int = 3, blink: bool = False,
           shake_t: float | None = None, hardcore: bool = False) -> bool:
    """Linha de corações (meio-coração = precisão). `blink` pisca após levar dano; `shake_t` treme em vida baixa."""
    pre = "hardcore_" if hardcore else ""
    cont = mc.sprite(HEART + ("container_blinking.png" if blink else "container.png"), k)
    full = mc.sprite(HEART + pre + ("full_blinking.png" if blink else "full.png"), k)
    half = mc.sprite(HEART + pre + ("half_blinking.png" if blink else "half.png"), k)
    if cont is None or full is None or half is None:
        return False
    step = 8 * k
    units = max(0.0, min(1.0, frac)) * count
    import math
    for i in range(count):
        yy = y + (int(2 * math.sin(shake_t * 22 + i * 1.7)) if shake_t is not None else 0)
        surf.blit(cont, (x + i * step, yy))
        if units >= i + 1 - 1e-6:
            surf.blit(full, (x + i * step, yy))
        elif units >= i + 0.5 - 1e-6:
            surf.blit(half, (x + i * step, yy))
    return True


def icons(surf, x: int, y: int, frac: float, kind: str, *, count: int = 10, k: int = 2, rtl: bool = False) -> bool:
    """Linha de ícones de status: kind = 'food' (estamina) ou 'armor' (armadura/poise)."""
    names = {"food": ("food_empty", "food_half", "food_full"), "armor": ("armor_empty", "armor_half", "armor_full")}[kind]
    sprites = [mc.sprite(HUD + n + ".png", k) for n in names]
    if any(s is None for s in sprites):
        return False
    empty, half, full = sprites
    step = 8 * k
    units = max(0.0, min(1.0, frac)) * count
    for i in range(count):
        ix = x - i * step if rtl else x + i * step
        surf.blit(empty, (ix, y))
        if units >= i + 1 - 1e-6:
            surf.blit(full, (ix, y))
        elif units >= i + 0.5 - 1e-6:
            surf.blit(half, (ix, y))
    return True


def boss_bar(surf, rect: pygame.Rect, frac: float, color: str = "red", notches: int = 0, rtl: bool = False) -> bool:
    """Barra de chefe: fundo + progresso recortado. notches = 6/10/12/20 sobrepõe as divisórias (como no jogo)."""
    bg = mc.stretch(BOSS + color + "_background.png", rect.size)
    fg = mc.stretch(BOSS + color + "_progress.png", rect.size)
    if bg is None or fg is None:
        return False
    nbg = mc.stretch(BOSS + f"notched_{notches}_background.png", rect.size) if notches else None
    nfg = mc.stretch(BOSS + f"notched_{notches}_progress.png", rect.size) if notches else None
    surf.blit(bg, rect)
    if nbg is not None:
        surf.blit(nbg, rect)
    w = int(rect.w * max(0.0, min(1.0, frac)))
    if w > 0:
        src = pygame.Rect(rect.w - w if rtl else 0, 0, w, rect.h)
        surf.blit(fg, (rect.x + src.x, rect.y), src)
        if nfg is not None:
            surf.blit(nfg, (rect.x + src.x, rect.y), src)
    return True


def hotbar(surf, center_bottom: tuple[int, int], slots: list[dict], k: int = 3) -> bool:
    """Hotbar de golpes. Cada slot: {icon, active, dim (0..1 escurecimento), label}. Usa hotbar.png (9 espaços de 20 px)."""
    bar = mc.sprite(HUD + "hotbar.png", k)
    sel = mc.sprite(HUD + "hotbar_selection.png", k)
    if bar is None or sel is None:
        return False
    r = bar.get_rect(midbottom=center_bottom)
    surf.blit(bar, r)
    font = pygame.font.Font(None, 16 + 2 * k)
    for i, s in enumerate(slots):
        sx = r.x + (3 + i * 20) * k
        icon = mc.sprite(s["icon"], k) if s.get("icon") else None
        if icon is not None:
            if s.get("dim"):
                icon = icon.copy()
                v = int(255 * (1 - s["dim"]))
                icon.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(icon, (sx + k, r.y + 3 * k))
        if s.get("label"):
            txt = font.render(s["label"], True, (235, 235, 235))
            sh = font.render(s["label"], True, (30, 30, 30))
            pos = (sx + 9 * k - txt.get_width() // 2, r.bottom + 2)
            surf.blit(sh, (pos[0] + 1, pos[1] + 1))
            surf.blit(txt, pos)
        if s.get("active"):
            surf.blit(sel, (sx - 2 * k, r.y - k))
    return True
