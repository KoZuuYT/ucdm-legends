"""Pausa (Esc ou janela sem foco) para treinos e arena."""
from typing import Callable

import pygame

from core import ui
from core.scene import Scene
from scenes.dialogs import ConfirmDialog
from systems.tween import ease_out_cubic


class PauseOverlay(Scene):
    transparent = True
    dim_alpha = 150
    GRACE = 0.2

    def __init__(self, game, on_quit: Callable[[], None], on_restart: Callable[[], None] | None = None,
                 info: list[str] | None = None) -> None:
        super().__init__(game)
        self.on_quit, self.on_restart = on_quit, on_restart
        self.info = info or []                      # linhas de resumo (luta, vida...)
        self.t = 0.0
        W, H = game.display.width, game.display.height
        extra = 30 * len(self.info)
        self.panel = pygame.Rect(0, 0, 460, 400 + extra + (74 if on_restart else 0) + 74)
        self.panel.center = (W // 2, H // 2)
        x, w = self.panel.x + 50, self.panel.w - 100
        items = [("Continuar", self._resume)]
        if on_restart:
            items.append(("Reiniciar luta", self._restart))
        items += [("Opções", self._options), ("Ajuda", self._help), ("Desistir", self._quit)]
        self._base = [110 + extra + i * 74 for i in range(len(items))]
        self.menu = ui.Menu([ui.Button((x, self.panel.y + y, w, 58), lab, fn) for (lab, fn), y in zip(items, self._base)])
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 150))

    def _resume(self) -> None:
        self.game.scenes.pop()

    def _help(self) -> None:
        from scenes.help import HelpOverlay
        self.game.scenes.push(HelpOverlay(self.game))

    def _restart(self) -> None:
        self.game.scenes.push(ConfirmDialog(
            self.game, "Reiniciar a luta?", "A luta atual recomeça do zero, sem recompensa pela tentativa.",
            on_yes=self._do_restart, yes_label="Reiniciar"))

    def _do_restart(self) -> None:
        self.game.scenes.pop()      # fecha a pausa
        self.on_restart()

    def _options(self) -> None:
        from scenes.options import OptionsScene
        self.game.scenes.push(OptionsScene(self.game), fade="slide")

    def _quit(self) -> None:
        self.game.scenes.push(ConfirmDialog(
            self.game, "Desistir?", "O treino/luta atual termina sem recompensa.\nSeu progresso salvo não é afetado.",
            on_yes=self._do_quit, yes_label="Desistir", danger=True))

    def _do_quit(self) -> None:
        self.game.scenes.pop()      # fecha a pausa
        self.on_quit()

    def update(self, dt: float) -> None:
        self.t += dt
        self.game.audio.duck(0.3)      # música mais baixa enquanto pausado
        if self.t < self.GRACE:
            return
        if self.game.input.pressed("back"):
            ui.sfx("back")
            return self._resume()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        k = ease_out_cubic(min(1.0, self.t / 0.2))
        off = int((1 - k) * 40)
        a = self.game.assets
        ui.panel(surf, self.panel.move(0, off), (20, 22, 32, 235))
        ui.text(surf, a.font(48), "PAUSADO", (self.panel.centerx, self.panel.top + 26 + off), ui.ACCENT, "midtop")
        for i, line in enumerate(self.info):
            ui.text(surf, a.font(20, bold=False), line, (self.panel.centerx, self.panel.top + 96 + i * 30 + off),
                    (210, 212, 225), "midtop")
        for b, base in zip(self.menu.buttons, self._base):
            b.rect.y = self.panel.y + base + off
        self.menu.draw(surf, a.font(30))
