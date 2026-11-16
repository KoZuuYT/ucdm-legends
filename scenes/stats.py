"""Estatísticas do treinador, recordes e diário da arena (tudo vem do save local)."""
import pygame

from core import config, ui
from core.scene import Scene
from entities import roster
from scenes.save_select import fmt_time
from systems import backdrop


class StatsScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.scenery = backdrop.Scenery(game, "night", 600)

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if self.t > 0.15 and (inp.pressed("back") or inp.pressed("confirm") or inp.taps):
            ui.sfx("back")
            self.game.scenes.pop(fade="slide")

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        p = self.game.profile
        self.scenery.draw(surf, self.t)
        ui.text(surf, a.font(52), "Estatísticas", (W // 2, 24), ui.ACCENT, "midtop")
        c = p.counters
        ui.panel(surf, (40, 100, 560, 560))
        rows = [("Tempo de jogo", fmt_time(p.playtime)), ("Ouro", p.gold), ("Nível da arma", p.weapon_level),
                ("Lutas vencidas", c.get("fights_won", p.wins)), ("Derrotas", c.get("losses", 0)),
                ("Parries", c.get("parries", 0)), ("Esquivas", c.get("dodges", 0)),
                ("Golpes acertados", c.get("hits_landed", 0)), ("Críticos", c.get("crits", 0)),
                ("Dano total", c.get("damage_dealt", 0)), ("Maior golpe", c.get("max_hit", 0))]
        for i, (k, v) in enumerate(rows):
            y = 124 + i * 42
            ui.text(surf, a.font(24, bold=False), k, (70, y))
            ui.text(surf, a.font(26), v, (570, y), ui.ACCENT, "topright")
        # recordes + diário
        ui.panel(surf, (630, 100, 610, 560))
        ui.text(surf, a.font(30), "Recordes dos treinos", (660, 114), ui.ACCENT)
        mg = config.load("minigames")
        y = 156
        for key, cfg in mg.items():
            ui.text(surf, a.font(22, bold=False), cfg.get("title", key), (660, y))
            ui.text(surf, a.font(24), p.best_scores.get(key, 0), (1210, y), ui.WHITE, "topright")
            y += 34
        y += 14
        ui.text(surf, a.font(30), "Diário da arena", (660, y), ui.ACCENT)
        y += 42
        for i, e in enumerate(roster.enemies()):
            name = roster.character(e["character"])["name"]
            if i < p.arena_stage:
                state, col = "derrotado", ui.GREEN
            elif i == p.arena_stage:
                state, col = "próximo", ui.ACCENT
            else:
                state, col = "bloqueado", (130, 130, 140)
            ui.text(surf, a.font(20, bold=False), f"{i + 1}. {name if i <= p.arena_stage else '???'}", (660, y), col)
            ui.text(surf, a.font(20, bold=False), state, (1210, y), col, "topright")
            y += 30
        ui.text(surf, a.font(18, bold=False), "Esc / Enter para voltar", (W // 2, H - 26), (190, 190, 200), "midbottom")
