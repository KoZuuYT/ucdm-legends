"""Menu principal."""
import math
import random

import pygame

from core import paths, ui
from core.scene import Scene
from entities import roster
from entities.progression import Profile
from systems import backdrop


def _read_version() -> str:
    import json
    try:
        return json.loads(paths.VERSION_FILE.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "dev"


class MenuScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.version = _read_version()
        chars = roster.characters()
        self.parade = random.sample(chars, k=min(7, len(chars)))
        self._build()

    def _build(self) -> None:
        W = self.game.display.width
        focus = self.menu.focus if hasattr(self, "menu") else 0
        buttons = []
        y = 330
        if self.game.save.exists():
            buttons.append(ui.Button((W // 2 - 170, y, 340, 58), "Continuar", self._continue))
            y += 68
        buttons.append(ui.Button((W // 2 - 170, y, 340, 58), "Saves", self._saves))
        buttons.append(ui.Button((W // 2 - 170, y + 68, 340, 58), "Opções", self._options))
        buttons.append(ui.Button((W // 2 - 170, y + 136, 340, 58), "Sair", self._ask_quit))
        self.menu = ui.Menu(buttons)
        self.menu.focus = min(focus, len(buttons) - 1)

    def enter(self) -> None:
        self.game.audio.music("menu")

    def resume(self) -> None:
        self.game.audio.music("menu")
        self._build()

    def _continue(self) -> None:
        data = self.game.save.load_raw()
        if data is None:
            return self._saves()
        self.game.profile = Profile.from_dict(data)
        if data.get("_from_backup"):
            self.game.feedback.toast("Save principal corrompido: carregado do backup.", ui.ACCENT, 4.0)
        from scenes.hub import HubScene
        self.game.scenes.replace(HubScene(self.game), fade="iris")

    def _saves(self) -> None:
        from scenes.save_select import SaveSelectScene
        self.game.scenes.push(SaveSelectScene(self.game), fade="slide")

    def _options(self) -> None:
        from scenes.options import OptionsScene
        self.game.scenes.push(OptionsScene(self.game), fade="slide")

    def _ask_quit(self) -> None:
        from scenes.dialogs import ConfirmDialog
        self.game.scenes.push(ConfirmDialog(self.game, "Sair do jogo?", "Seu progresso já está salvo.",
                                            on_yes=self.game.quit, yes_label="Sair"))

    def update(self, dt: float) -> None:
        self.t += dt
        if self.game.input.pressed("back"):
            return self._ask_quit()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        surf.blit(backdrop.build("dusk", (W, H), 620, self.game.assets), (0, 0))
        for i, c in enumerate(self.parade):
            x = 90 + i * (W - 180) / max(1, len(self.parade) - 1)
            y = 640 + 8 * math.sin(self.t * 3 + i)
            img = self.game.assets.image_h(c["sprite"], 150)
            surf.blit(img, img.get_rect(midbottom=(x, y)))
        title = self.game.cfg["title"]
        ui.text(surf, self.game.assets.font(96), title, (W // 2, 110 + 6 * math.sin(self.t * 2)), ui.ACCENT, "midtop")
        ui.text(surf, self.game.assets.font(26), "Treine. Lute. Evolua.", (W // 2, 230), anchor="midtop")
        self.menu.draw(surf, self.game.assets.font(32))
        ui.text(surf, self.game.assets.font(18), f"v{self.version}", (W - 12, H - 10), (200, 200, 200), "bottomright")
