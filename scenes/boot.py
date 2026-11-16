"""Tela de boot: checa/baixa atualizações ANTES do menu, sem travar a janela.
Sem internet ou sem repo configurado, segue direto para o menu."""
import math

import pygame

from core import ui
from core.scene import Scene
from network.updater import UpdateTask, can_self_update


class BootScene(Scene):
    MIN_TIME = 0.6
    CHECK_TIMEOUT = 10.0

    def __init__(self, game) -> None:
        super().__init__(game)
        self.task = UpdateTask(game.cfg.get("update", {}))
        self.t = 0.0
        self.hold = 0.0      # tempo extra para exibir mensagens

    def enter(self) -> None:
        self.task.start_check()

    def _to_menu(self) -> None:
        from scenes.menu import MenuScene
        self.game.scenes.replace(MenuScene(self.game))
        self.t = -999  # evita trocar duas vezes

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t < 0:
            return
        task = self.task
        if self.game.input.pressed("back"):
            task.cancel()
            return self._to_menu()
        st = task.state
        if st in ("none", "error", "idle") and self.t >= self.MIN_TIME:
            return self._to_menu()
        if st == "checking" and self.t > self.CHECK_TIMEOUT:
            return self._to_menu()
        if st == "available":
            if can_self_update():
                task.start_download()
                task.state = "downloading"
            else:
                self.hold += dt
                task.message = f"{task.info.version} disponível — modo desenvolvimento: use git pull"
                if self.hold > 2.0:
                    return self._to_menu()
        if st == "ready":
            if task.apply_and_restart():
                self.game.quit()
            else:
                self._to_menu()

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        surf.fill((18, 20, 30))
        a = self.game.assets
        ui.text(surf, a.font(64), self.game.cfg["title"], (W // 2, H // 2 - 120), ui.ACCENT, "center")
        msg = self.task.message or "Iniciando..."
        ui.text(surf, a.font(24), msg, (W // 2, H // 2 + 10), anchor="center")
        if self.task.state == "downloading":
            ui.bar(surf, (W // 2 - 250, H // 2 + 50, 500, 22), self.task.progress, ui.GREEN)
        for i in range(8):
            ang = self.t * 4 + i * math.tau / 8
            r = 4 + (i / 8) * 4
            pygame.draw.circle(surf, ui.WHITE, (W // 2 + math.cos(ang) * 26, H // 2 + 110 + math.sin(ang) * 26), r)
        ui.text(surf, a.font(16), "Esc para pular", (W // 2, H - 30), (150, 150, 160), "center")
