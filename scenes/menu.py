"""Menu principal."""
import json
import math
import random

import pygame

from core import paths, ui
from core.i18n import tr
from core.scene import Scene
from entities import roster
from entities.progression import Profile
from core import config, theme
from systems import backdrop, menu_fx, pulse


def _read_version() -> str:
    import json
    try:
        return json.loads(paths.VERSION_FILE.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "dev"


class MenuScene(Scene):
    wide = True
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.version = _read_version()
        chars = roster.characters()
        self.scenery = backdrop.Scenery(game, "dusk", 620)
        self.parade = random.sample(chars, k=min(7, len(chars)))
        self.splash_text = random.choice(config.load("menu")["splashes"])
        self._build()

    def on_resize(self, canvas_w: int) -> None:
        self._build()

    def _build(self) -> None:
        W = self.game.display.canvas_w
        focus = self.menu.focus if hasattr(self, "menu") else 0
        buttons = []
        y = 330
        from network.updater import can_self_update
        if self.game.update_notice and can_self_update():
            buttons.append(ui.Button((W // 2 - 170, y, 340, 58), "Atualizar agora", self._update_now))
            y += 68
        if self.game.save.exists():
            buttons.append(ui.Button((W // 2 - 170, y, 340, 62), "Continuar", self._continue, sub=self._save_line()))
            y += 72
        buttons.append(ui.Button((W // 2 - 170, y, 340, 58), "Saves", self._saves))
        buttons.append(ui.Button((W // 2 - 170, y + 68, 340, 58), "Opções", self._options))
        buttons.append(ui.Button((W // 2 - 170, y + 136, 340, 58), "Sair", self._ask_quit))
        self.menu = ui.Menu(buttons)
        self.menu.focus = min(focus, len(buttons) - 1)

    def _save_line(self) -> str:
        """Resumo do save atual no botão Continuar: 'Nv 4 · Luta 3/8 · 120 ouro'."""
        s = self.game.save.summary()
        if not s:
            return ""
        n = len(roster.enemies())
        return f"Nv {s['level']}  ·  Luta {min(s['arena_stage'] + 1, n)}/{n}  ·  {s['gold']} ouro"

    def _update_now(self) -> None:
        from scenes.boot import BootScene
        self.game.scenes.reset(BootScene(self.game))

    def _show_news(self) -> None:
        """Depois de atualizar, mostra as novidades uma vez (a versão vista fica em settings.json)."""
        from core import settings
        from scenes.news import NewsOverlay
        if self.version == "dev" or self.game.cfg.get("last_seen_version") == self.version:
            return
        notes = ""
        try:
            notes = json.loads(paths.VERSION_FILE.read_text(encoding="utf-8")).get("notes", "")
        except (OSError, ValueError):
            pass
        settings.set_value("last_seen_version", self.version)
        self.game.cfg["last_seen_version"] = self.version
        if notes:
            self.game.scenes.push(NewsOverlay(self.game, self.version, notes))

    def enter(self) -> None:
        self.game.audio.music("menu")
        self._show_news()

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

    def _title_shine(self, surf: pygame.Surface, rect: pygame.Rect, title: str) -> None:
        """Faixa de luz que atravessa as letras do título de tempos em tempos (só dentro do desenho do texto)."""
        if self.game.feedback.reduce_motion or self.game.low_perf:
            return
        p = (self.t % 4.5) / 1.2                              # 1,2 s de brilho a cada 4,5 s
        if p > 1.0:
            return
        head = ui._heading(self.game.assets.font(96), title, ui.ACCENT)
        mask = ui._remember(("shinemask", head.get_size(), title), lambda: pygame.mask.from_surface(head, 80).to_surface(
            setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)))
        band = ui._sheen()
        tmp = pygame.Surface(head.get_size(), pygame.SRCALPHA)
        sc = pygame.transform.smoothscale(band, (band.get_width() * 2, head.get_height()))
        tmp.blit(sc, (-sc.get_width() + p * (head.get_width() + sc.get_width() * 2), 0))
        tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(tmp, (rect.x - 4, rect.y - 4), special_flags=pygame.BLEND_RGB_ADD)

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        mc_look = theme.mc() and not ui.high_contrast
        if not (mc_look and menu_fx.draw_panorama(surf, self.t)):
            self.scenery.draw(surf, self.t)
        a = self.game.assets
        who = self.game.profile.character if self.game.profile else "steve"
        hero = a.image_h(roster.character(who)["sprite"], 320)
        surf.blit(hero, hero.get_rect(midbottom=(int(W * 0.17), 650 + 5 * math.sin(self.t * 2))))
        for i, c in enumerate(self.parade):
            x = 90 + i * (W - 180) / max(1, len(self.parade) - 1)
            y = 640 + 8 * math.sin(self.t * 3 + i)
            look = 1 if x < W / 2 else -1                      # cada um olha para o centro
            img = self.game.assets.image_h(c["sprite"], 150, look != c.get("faces", -1))
            surf.blit(img, img.get_rect(midbottom=(x, y)))
        title = self.game.cfg["title"]
        if mc_look:
            logo = menu_fx.extruded_title(a.font(88), title)
            if not self.game.feedback.reduce_motion:            # o logo "bate" no ritmo
                k = 1.0 + 0.025 * pulse.beat(self.t)
                logo = pygame.transform.smoothscale(logo, (int(logo.get_width() * k), int(logo.get_height() * k)))
            lr = logo.get_rect(midtop=(W // 2, 100 + int(4 * math.sin(self.t * 2))))
            surf.blit(logo, lr)
            sp = menu_fx.splash(a.font(24), tr(self.splash_text), self.t, self.game.feedback.reduce_motion)
            surf.blit(sp, sp.get_rect(center=(lr.right - 40, lr.bottom - 6)))
        else:
            tr_ = ui.text(surf, a.font(96), title, (W // 2, 110 + 6 * math.sin(self.t * 2)), ui.ACCENT, "midtop")
            self._title_shine(surf, tr_, title)
            ui.text(surf, a.font(26), "Treine. Lute. Evolua.", (W // 2, 230), anchor="midtop")
        if self.game.update_notice:
            from network.updater import can_self_update
            msg = (f"Nova versão {self.game.update_notice} disponível!" if can_self_update()
                   else f"Nova versão {self.game.update_notice} disponível (use git pull)")
            ui.text(surf, self.game.assets.font(22), msg, (W // 2, 282), ui.GREEN, "midtop")
        self.menu.draw(surf, a.font(32), a.font(17, bold=False))
        ui.text(surf, a.font(16, bold=False), "Enter: selecionar    Esc: sair    F11: tela cheia", (16, H - 10),
                (200, 200, 210), "bottomleft")
        ui.text(surf, self.game.assets.font(18), f"v{self.version}", (W - 12, H - 10), (200, 200, 200), "bottomright")
