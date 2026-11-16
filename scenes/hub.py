"""Hub: centro do loop de progressão (treinar -> lutar -> melhorar arma)."""
import math

import pygame

from core import config, ui
from core.scene import Scene
from entities import roster
from entities.progression import STATS, weapon_cost, xp_to_next
from minigames import REGISTRY
from systems import backdrop


class HubScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.toast = ("", 0.0)
        self._build()

    def _build(self) -> None:
        p = self.game.profile
        bal = config.load("balance")["stats"]
        mg = config.load("minigames")
        buttons: list[ui.Button] = []
        x0, y0 = 470, 150
        for i, stat in enumerate(STATS):
            key = bal[stat]["trained_by"]
            if key in REGISTRY:
                buttons.append(ui.Button((x0 + (i % 2) * 300, y0 + (i // 2) * 96, 280, 80), mg[key]["title"],
                                         lambda k=key: self._train(k), sub=f"{bal[stat]['label']} nv {p.level(stat)}"))
        enemies = roster.enemies()
        if p.arena_stage < len(enemies):
            e = enemies[p.arena_stage]
            sub = f"Luta {p.arena_stage + 1}/{len(enemies)}: {roster.character(e['character'])['name']}"
            buttons.append(ui.Button((x0, y0 + 210, 580, 90), "ARENA", self._arena, sub=sub))
        else:
            buttons.append(ui.Button((x0, y0 + 210, 580, 90), "ARENA (revanche)", self._arena,
                                     sub="Campeão! Enfrente o chefe de novo"))
        cost = weapon_cost(p.weapon_level)
        buttons.append(ui.Button((x0, y0 + 320, 280, 70), f"Arma nv {p.weapon_level + 1}", self._upgrade,
                                 enabled=p.gold >= cost, sub=f"{cost} ouro"))
        buttons.append(ui.Button((x0 + 300, y0 + 320, 280, 70), "Trocar lutador", self._change_char))
        buttons.append(ui.Button((x0, y0 + 396, 280, 52), "Estatísticas", self._stats))
        buttons.append(ui.Button((x0 + 300, y0 + 396, 280, 52), "Ajuda", self._help))
        buttons.append(ui.Button((x0, y0 + 458, 280, 52), "Opções", self._options))
        buttons.append(ui.Button((x0 + 300, y0 + 458, 280, 52), "Menu principal", self._to_menu))
        focus = self.menu.focus if hasattr(self, "menu") else 0
        self.menu = ui.Menu(buttons, columns=2)
        self.menu.focus = min(focus, len(buttons) - 1)

    # --- ações ------------------------------------------------------------------------
    def _train(self, key: str) -> None:
        self.game.scenes.push(REGISTRY[key](self.game), fade=True)

    def _arena(self) -> None:
        from scenes.arena import ArenaScene
        enemies = roster.enemies()
        stage = min(self.game.profile.arena_stage, len(enemies) - 1)
        self.game.scenes.push(ArenaScene(self.game, stage), fade="iris")

    def _upgrade(self) -> None:
        p = self.game.profile
        cost = weapon_cost(p.weapon_level)
        if p.gold >= cost:
            p.gold -= cost
            p.weapon_level += 1
            self.game.save.save(p)
            self.game.audio.play("coin")
            self.toast = (f"Arma melhorada para o nível {p.weapon_level}!", 2.0)
            self._build()

    def _change_char(self) -> None:
        from scenes.character_select import CharacterSelectScene
        self.game.scenes.push(CharacterSelectScene(self.game, new_game=False), fade="slide")

    def _stats(self) -> None:
        from scenes.stats import StatsScene
        self.game.scenes.push(StatsScene(self.game), fade="slide")

    def _help(self) -> None:
        from scenes.help import HelpOverlay
        self.game.scenes.push(HelpOverlay(self.game))

    def _options(self) -> None:
        from scenes.options import OptionsScene
        self.game.scenes.push(OptionsScene(self.game), fade="slide")

    def _to_menu(self) -> None:
        self.game.save.save(self.game.profile)
        from scenes.menu import MenuScene
        self.game.scenes.reset(MenuScene(self.game))

    # --- ciclo ------------------------------------------------------------------------
    def enter(self) -> None:
        self.game.audio.music("hub")
        p = self.game.profile
        if p is not None and not p.seen_help:     # tutorial da primeira vez (pode ser pulado com Esc)
            p.seen_help = True
            self.game.save.save(p)
            from scenes.help import HelpOverlay
            self.game.scenes.push(HelpOverlay(self.game))

    def resume(self) -> None:
        self.game.audio.music("hub")
        self._build()

    def update(self, dt: float) -> None:
        self.t += dt
        self.toast = (self.toast[0], self.toast[1] - dt)
        if self.game.input.pressed("back"):
            return self._to_menu()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        p = self.game.profile
        surf.blit(backdrop.build("meadow", (W, H), 600, a), (0, 0))
        ch = roster.character(p.character)
        img = a.image_h(ch["sprite"], 300)
        if img.get_width() > 340:
            img = a.image_h(ch["sprite"], int(300 * 340 / img.get_width()))
        surf.blit(img, img.get_rect(midbottom=(220, 620 + 4 * math.sin(self.t * 2))))

        # painel de atributos
        ui.panel(surf, (24, 20, 400, 300))
        ui.text(surf, a.font(32), ch["name"], (44, 34), ui.ACCENT)
        ui.text(surf, a.font(22), f"Ouro: {p.gold}    Vitórias: {p.wins}", (44, 74))
        bal = config.load("balance")["stats"]
        for i, stat in enumerate(STATS):
            s = p.stats[stat]
            y = 116 + i * 48
            ui.text(surf, a.font(20), f"{bal[stat]['label']}  nv {s.level}", (44, y))
            ui.bar(surf, (44, y + 24, 360, 14), s.xp / xp_to_next(s.level), tuple(bal[stat]["color"]))

        ui.text(surf, a.font(40), "Campo de Treino", (760, 80), ui.WHITE, "midtop")
        self.menu.draw(surf, a.font(28), a.font(18, bold=False))
        if self.toast[1] > 0:
            ui.text(surf, a.font(28), self.toast[0], (W // 2, H - 40), ui.GREEN, "center")
