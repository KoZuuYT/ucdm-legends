"""Tela de boot: checa/baixa atualizações ANTES do menu, sem travar a janela.
Sem internet ou sem repo configurado, segue direto para o menu."""
import math

import pygame

import random

from core import config, mcassets as mc, theme, ui
from core.i18n import tr
from systems import menu_fx
from systems.tween import ease_out_cubic
from core.scene import Scene
from network.updater import UpdateTask, can_self_update


class BootScene(Scene):
    wide = True
    MIN_TIME = 0.6
    CHECK_TIMEOUT = 10.0

    def __init__(self, game) -> None:
        super().__init__(game)
        self.task = UpdateTask(game.cfg.get("update", {}))
        self.t = 0.0
        self.hold = 0.0      # tempo extra para exibir mensagens
        self.tips = random.sample(config.load("menu")["tips"], k=3)

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
        mc_look = theme.mc() and not ui.high_contrast
        if not (mc_look and menu_fx.draw_panorama(surf, self.t)):
            ui.backdrop(surf, self.t)
        a = self.game.assets
        # logo "carimbado": entra grande e bate no lugar com um tremor curto
        k = max(0.0, min(1.0, self.t / 0.6))
        scale = 1.0 + 0.7 * (1 - ease_out_cubic(k))
        title = self.game.cfg["title"]
        if mc_look:
            logo = menu_fx.extruded_title(a.font(80), title)
        else:
            logo = ui._heading(a.font(72), title, ui.ACCENT)
        if scale > 1.005:
            logo = pygame.transform.smoothscale(logo, (int(logo.get_width() * scale), int(logo.get_height() * scale)))
        shake = int(6 * math.sin(self.t * 70)) if 0.55 < self.t < 0.75 and not self.game.feedback.reduce_motion else 0
        surf.blit(logo, logo.get_rect(center=(W // 2 + shake, H // 2 - 120)))
        msg = self.task.message or "Iniciando..."
        ui.text(surf, a.font(24), msg, (W // 2, H // 2 + 10), anchor="center")
        if self.task.state == "downloading":
            if mc_look:
                bg = mc.stretch(mc.GUI + "hud/experience_bar_background.png", (500, 14))
                fg = mc.stretch(mc.GUI + "hud/experience_bar_progress.png", (500, 14))
                if bg and fg:
                    surf.blit(bg, (W // 2 - 250, H // 2 + 54))
                    surf.blit(fg, (W // 2 - 250, H // 2 + 54), (0, 0, int(500 * self.task.progress), 14))
            else:
                ui.bar(surf, (W // 2 - 250, H // 2 + 50, 500, 22), self.task.progress, ui.GREEN)
        tip = self.tips[int(self.t / 3.0) % len(self.tips)]
        ui.text(surf, a.font(20, bold=False), f"{tr('Dica')}: {tr(tip)}", (W // 2, H - 70), (225, 225, 235), "center")
        for i in range(8):
            ang = self.t * 4 + i * math.tau / 8
            r = 4 + (i / 8) * 4
            pygame.draw.circle(surf, ui.WHITE, (W // 2 + math.cos(ang) * 26, H // 2 + 110 + math.sin(ang) * 26), r)
        ui.text(surf, a.font(16), "Esc para pular", (W // 2, H - 30), (150, 150, 160), "center")
