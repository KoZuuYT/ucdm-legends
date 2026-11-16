"""Modo atração: depois de um tempo parado no menu, uma luta de demonstração (Steve controlado pela IA)."""
import random

import pygame

from core import ui
from core.i18n import tr
from entities import roster
from entities.ai import EnemyBrain
from entities.progression import Profile
from scenes.arena import ArenaScene


class AttractScene(ArenaScene):
    IDLE_SECONDS = 45.0

    def __init__(self, game) -> None:
        self._saved = game.profile
        if game.profile is None:                       # no menu principal ainda não há save carregado
            game.profile = Profile()
        super().__init__(game, random.randint(1, max(1, len(roster.enemies()) - 2)))
        self.attract = True
        self.pbrain = EnemyBrain(self.player, self.enemy, {"aggression": 0.7, "block_chance": 0.3, "dodge_chance": 0.2,
                                                           "parry_skill": 0.35, "cooldown": [0.6, 1.4]})
        self.blink = 0.0

    def _set_touch_buttons(self) -> None:
        self.game.input.set_virtual_buttons([])

    def _wants_exit(self) -> bool:
        inp = self.game.input
        return bool(inp.taps) or any(inp.pressed(a) for a in ("confirm", "back", "attack", "block", "dodge", "left", "right", "up", "down"))

    def update(self, dt: float) -> None:
        self.blink += dt
        if self.blink > 0.4 and self._wants_exit():
            return self._leave()
        if not self.in_intro and self.result is None:
            self.pbrain.update(dt, self.now)
        super().update(dt)

    def _leave(self) -> None:
        self.game.scenes.pop(fade=True)

    def _finish(self) -> None:                         # a demonstração não mexe no save
        self._leave()

    def exit(self) -> None:
        super().exit()
        self.game.profile = self._saved

    def draw(self, surf: pygame.Surface) -> None:
        super().draw(surf)
        if int(self.blink * 1.6) % 2 == 0:
            ui.text(surf, self.game.assets.font(30), tr("DEMONSTRAÇÃO — pressione qualquer tecla"),
                    (surf.get_width() // 2, surf.get_height() - 36), ui.WHITE, "midbottom")
