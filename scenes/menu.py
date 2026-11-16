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
        buttons = []
        y = 360
        if self.game.save.exists():
            buttons.append(ui.Button((W // 2 - 170, y, 340, 60), "Continuar", self._continue))
            y += 76
        buttons.append(ui.Button((W // 2 - 170, y, 340, 60), "Novo jogo", self._new))
        buttons.append(ui.Button((W // 2 - 170, y + 76, 340, 60), "Sair", self.game.quit))
        self.menu = ui.Menu(buttons)

    def enter(self) -> None:
        self.game.audio.music("menu")

    def resume(self) -> None:
        self._build()

    def _continue(self) -> None:
        data = self.game.save.load_raw()
        if data is None:
            return self._new()
        self.game.profile = Profile.from_dict(data)
        from scenes.hub import HubScene
        self.game.scenes.replace(HubScene(self.game))

    def _new(self) -> None:
        from scenes.character_select import CharacterSelectScene
        self.game.scenes.push(CharacterSelectScene(self.game, new_game=True), fade=True)

    def update(self, dt: float) -> None:
        self.t += dt
        if self.game.input.pressed("back"):
            self.game.quit()
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
