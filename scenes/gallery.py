"""Galeria de componentes (ferramenta de design): mostra todos os widgets no tema atual. Opções > Sistema ou `--scene gallery`.
Troque o tema (T) para comparar Torneio x Minecraft."""
import pygame

from core import config, mcui, theme, ui
from core.scene import Scene


class GalleryScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.buttons = [ui.Button((60, 130, 260, 56), "Normal", lambda: None),
                        ui.Button((340, 130, 260, 56), "Com subtítulo", lambda: None, sub="texto pequeno"),
                        ui.Button((620, 130, 260, 56), "Desativado", lambda: None, enabled=False)]

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if inp.pressed("back"):
            return self.game.scenes.pop(fade=True)
        if inp.pressed("dodge") or inp.taps:                      # alterna o tema para comparar
            theme.set_theme("torneio" if theme.name == "minecraft" else "minecraft")
            self.game.assets._fonts.clear()

    def draw(self, surf: pygame.Surface) -> None:
        a = self.game.assets
        ui.backdrop(surf, self.t)
        ui.text(surf, a.font(40), f"Galeria — tema: {theme.info().get('label', theme.name)}", (60, 30), ui.ACCENT)
        ui.text(surf, a.font(18, bold=False), "Esquiva/toque: alternar tema   Esc: voltar", (60, 84), (200, 200, 215))
        for i, b in enumerate(self.buttons):
            b.draw(surf, a.font(26), i == 1 and int(self.t) % 2 == 0, a.font(18, bold=False))
        ui.panel(surf, (60, 220, 420, 150))
        ui.text(surf, a.font(24), "Painel", (80, 236), ui.WHITE)
        ui.bar(surf, (80, 290, 380, 16), 0.65, ui.GREEN)
        ui.bar(surf, (80, 320, 380, 16), 0.4, ui.BLUE)
        ui.row(surf, pygame.Rect(520, 230, 360, 44), focused=True)
        ui.row(surf, pygame.Rect(520, 282, 360, 44), active=True)
        ui.row(surf, pygame.Rect(520, 334, 360, 36))
        if theme.mc():
            mcui.hearts(surf, 60, 400, 0.7)
            mcui.icons(surf, 60, 440, 0.8, "food")
            mcui.icons(surf, 60, 470, 0.6, "armor")
            mcui.boss_bar(surf, pygame.Rect(60, 510, 420, 18), 0.6, "red", notches=10)
            mcui.checkbox(surf, (560, 420), True, False)
            mcui.checkbox(surf, (610, 420), False, True)
            mcui.slider(surf, pygame.Rect(520, 450, 360, 20), 0.4, True)
            mcui.hotbar(surf, (480, 650), [{"icon": "item/iron_sword.png", "active": True, "label": "A"},
                                           {"icon": "item/iron_chestplate.png"}, {"icon": "item/feather.png", "dim": 0.6}], k=3)
        else:
            ui.text(surf, a.font(20), "Tema Torneio: widgets desenhados em código.", (60, 410), (200, 200, 215))
        for i, (name, col) in enumerate((("accent", ui.ACCENT), ("red", ui.RED), ("green", ui.GREEN), ("blue", ui.BLUE), ("white", ui.WHITE))):
            pygame.draw.rect(surf, col, (940, 130 + i * 56, 60, 44))
            ui.text(surf, a.font(18), name, (1010, 140 + i * 56), ui.WHITE)
        for i, size in enumerate((16, 20, 24, 32, 46)):
            ui.text(surf, a.font(size), f"Texto {size}px Áã Çõ", (900, 420 + i * 48), ui.WHITE)
