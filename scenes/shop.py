"""Loja de cosméticos: gasta ouro em cores para os efeitos de golpe e de esquiva do Steve (só visual)."""
import colorsys

import pygame

from core import config, ui
from core.i18n import tr
from core.scene import Scene
from systems import backdrop


def items() -> list[dict]:
    return config.load("shop")["items"]


def item(item_id: str) -> dict | None:
    return next((i for i in items() if i["id"] == item_id), None)


def color_of(item_id: str, now: float = 0.0) -> tuple | None:
    """Cor do cosmético equipado (None = efeito padrão). "rainbow" gira com o tempo."""
    it = item(item_id) if item_id else None
    if it is None:
        return None
    if it.get("rainbow"):
        r, g, b = colorsys.hsv_to_rgb((now * 0.7) % 1.0, 0.65, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)
    return tuple(it["color"])


def owned(profile, item_id: str) -> bool:
    it = item(item_id)
    return bool(it) and (it.get("price", 0) == 0 or item_id in profile.cosmetics)


def buy_or_equip(profile, item_id: str) -> str:
    """Compra (se couber no ouro) e equipa. Retorna "equipped", "bought", "poor" ou "unknown"."""
    it = item(item_id)
    if it is None:
        return "unknown"
    if owned(profile, item_id):
        profile.equipped[it["slot"]] = item_id
        return "equipped"
    if profile.gold < it["price"]:
        return "poor"
    profile.gold -= it["price"]
    profile.cosmetics.append(item_id)
    profile.equipped[it["slot"]] = item_id
    return "bought"


class ShopScene(Scene):
    SLOTS = (("fx_hit", "Efeito de golpe"), ("fx_dodge", "Efeito de esquiva"))

    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.slot = 0
        self.toast = ("", 0.0)
        self.scenery = backdrop.Scenery(game, "meadow", 600)
        self._build()

    @property
    def profile(self):
        return self.game.profile

    def _build(self) -> None:
        p = self.profile
        slot = self.SLOTS[self.slot][0]
        buttons = [ui.Button((110, 170, 200, 52), tr(self.SLOTS[0][1]), lambda: self._set_slot(0)),
                   ui.Button((320, 170, 200, 52), tr(self.SLOTS[1][1]), lambda: self._set_slot(1))]
        self.mine = [i for i in items() if i["slot"] == slot]
        for k, it in enumerate(self.mine):
            have = owned(p, it["id"])
            on = p.equipped.get(slot, "") == it["id"] or (not p.equipped.get(slot) and it.get("price", 0) == 0)
            sub = tr("Equipado") if on else (tr("Equipar") if have else f"{it['price']} {tr('ouro')}")
            buttons.append(ui.Button((110 + (k % 2) * 330, 250 + (k // 2) * 84, 310, 72), tr(it["name"]),
                                     lambda i=it: self._pick(i), enabled=have or p.gold >= it["price"], sub=sub))
        buttons.append(ui.Button((110, 620, 310, 56), "Voltar", lambda: self.game.scenes.pop(fade="slide")))
        focus = self.menu.focus if hasattr(self, "menu") else 2
        self.menu = ui.Menu(buttons, columns=2)
        self.menu.focus = min(focus, len(buttons) - 1)

    def _set_slot(self, i: int) -> None:
        self.slot = i
        self._build()
        self.menu.focus = 0

    def _pick(self, it: dict) -> None:
        res = buy_or_equip(self.profile, it["id"])
        msg = {"bought": "Comprado e equipado!", "equipped": "Equipado!", "poor": "Ouro insuficiente."}.get(res, "")
        self.toast = (tr(msg), 1.8)
        if res == "bought":
            self.game.audio.play("coin")
            self.game.save.save(self.profile)
        self._build()

    def update(self, dt: float) -> None:
        self.t += dt
        self.toast = (self.toast[0], self.toast[1] - dt)
        if self.game.input.pressed("back"):
            return self.game.scenes.pop(fade="slide")
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        a = self.game.assets
        ui.backdrop(surf, self.t, animate=not self.game.feedback.reduce_motion)
        ui.text(surf, a.font(44), tr("Loja"), (110, 60), ui.ACCENT)
        ui.text(surf, a.font(26), f"{tr('Ouro')}: {self.profile.gold}", (110, 118), ui.WHITE)
        self.menu.draw(surf, a.font(26), a.font(18, bold=False))
        for k, it in enumerate(self.mine):
            r = pygame.Rect(110 + (k % 2) * 330, 250 + (k // 2) * 84, 310, 72)
            c = color_of(it["id"], self.t) or (200, 200, 200)
            pygame.draw.rect(surf, c, (r.right - 54, r.y + 16, 36, 36))
            pygame.draw.rect(surf, (20, 20, 25), (r.right - 54, r.y + 16, 36, 36), 3)
        # prévia: pequenas partículas na cor equipada
        slot = self.SLOTS[self.slot][0]
        c = color_of(self.profile.equipped.get(slot, ""), self.t) or (255, 90, 70)
        cx, cy = 1000, 360
        ui.text(surf, a.font(24), tr("Prévia"), (cx, 230), ui.ACCENT, "center")
        for i in range(14):
            ang = i * 0.449 + self.t * 1.5
            rad = 40 + (i * 13 + self.t * 60) % 90
            pygame.draw.rect(surf, c, (cx + int(rad * pygame.math.Vector2(1, 0).rotate_rad(ang).x),
                                       cy + int(rad * pygame.math.Vector2(1, 0).rotate_rad(ang).y), 12, 12))
        if self.toast[1] > 0:
            ui.text(surf, a.font(26), self.toast[0], (640, 600), ui.GREEN, "center")
