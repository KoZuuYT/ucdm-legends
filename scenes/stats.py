"""Estatísticas do treinador, recordes e diário da arena (tudo vem do save local)."""
import math

import pygame

from core import config, ui
from core.scene import Scene
from entities import roster
from scenes.save_select import fmt_time
from systems import achievements, backdrop


class StatsScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.scenery = backdrop.Scenery(game, "night", 600)
        self.ach_btn = ui.Button((1280 - 330, 30, 290, 52), "Conquistas", self._open_ach,
                                 sub=f"{len(game.profile.achievements)}/{len(achievements.defs())}")

    def _history(self, surf, p, a, x: int, y: int) -> None:
        """Últimas 10 lutas: bolinha verde (vitória) ou vermelha (derrota)."""
        ui.text(surf, a.font(20), "Últimas lutas", (x, y), ui.ACCENT)
        hist = p.history[-10:]
        for i in range(10):
            cx, cy = x + 14 + (i % 5) * 36, y + 52 + (i // 5) * 36
            if i < len(hist):
                win = hist[i] == "W"
                pygame.draw.circle(surf, ui.GREEN if win else ui.RED, (cx, cy), 13)
                ui.text(surf, a.font(15), "V" if win else "D", (cx, cy), (15, 15, 20), "center", False)
            else:
                pygame.draw.circle(surf, (70, 72, 90), (cx, cy), 13, 2)

    def _radar(self, surf, p, a, center, radius: int) -> None:
        """Gráfico de radar dos 4 atributos (nível relativo ao maior entre eles, com piso 5)."""
        from entities.progression import STATS
        bal = config.load("balance")["stats"]
        top = max(5, max(p.level(s) for s in STATS))
        n = len(STATS)
        cx, cy = center
        for ring in (0.33, 0.66, 1.0):
            pts = [(cx + math.sin(2 * math.pi * i / n) * radius * ring, cy - math.cos(2 * math.pi * i / n) * radius * ring)
                   for i in range(n)]
            pygame.draw.polygon(surf, (90, 94, 118), pts, 1)
        vals = []
        for i, s in enumerate(STATS):
            k = p.level(s) / top
            ang = 2 * math.pi * i / n
            vals.append((cx + math.sin(ang) * radius * k, cy - math.cos(ang) * radius * k))
            lab = f"{bal[s]['label'][:3]} {p.level(s)}"
            ui.text(surf, a.font(15, bold=False), lab, (cx + math.sin(ang) * (radius + 14), cy - math.cos(ang) * (radius + 14)),
                    ui.stat_color(s, bal[s]["color"]), "center", False)
        shape = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        off = (cx - radius * 2, cy - radius * 2)
        pygame.draw.polygon(shape, (*ui.ACCENT, 90), [(x - off[0], y - off[1]) for x, y in vals])
        surf.blit(shape, off)
        pygame.draw.polygon(surf, ui.ACCENT, vals, 2)

    def _open_ach(self) -> None:
        from scenes.achievements_screen import AchievementsScene
        self.game.scenes.push(AchievementsScene(self.game), fade="slide")

    def resume(self) -> None:
        self.ach_btn.sub = f"{len(self.game.profile.achievements)}/{len(achievements.defs())}"

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        for pos in inp.taps:
            if self.ach_btn.rect.collidepoint(pos):
                return self.ach_btn.click(pos)
        if self.t > 0.15 and inp.pressed("dodge"):
            return self._open_ach()
        if self.t > 0.15 and (inp.pressed("back") or inp.pressed("confirm") or inp.taps):
            ui.sfx("back")
            self.game.scenes.pop(fade="slide")

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        p = self.game.profile
        self.scenery.draw(surf, self.t)
        ui.text(surf, a.font(52), "Estatísticas", (60, 24), ui.ACCENT, "topleft")
        c = p.counters
        ui.panel(surf, (40, 100, 560, 560))
        rows = [("Tempo de jogo", fmt_time(p.playtime)), ("Ouro", p.gold), ("Nível da arma", p.weapon_level),
                ("Lutas vencidas", c.get("fights_won", p.wins)), ("Derrotas", c.get("losses", 0)),
                ("Parries", c.get("parries", 0)), ("Esquivas", c.get("dodges", 0)),
                ("Golpes acertados", c.get("hits_landed", 0)), ("Críticos", c.get("crits", 0)),
                ("Dano total", c.get("damage_dealt", 0)), ("Maior golpe", c.get("max_hit", 0))]
        for i, (k, v) in enumerate(rows):
            y = 120 + i * 34
            ui.text(surf, a.font(22, bold=False), k, (70, y))
            ui.text(surf, a.font(24), v, (570, y), ui.ACCENT, "topright")
        self._history(surf, p, a, 70, 520)
        self._radar(surf, p, a, (450, 590), 56)
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
        self.ach_btn.draw(surf, a.font(24), False, a.font(16, bold=False))
        ui.text(surf, a.font(18, bold=False), "Esc / Enter para voltar    Esquiva: conquistas", (W // 2, H - 26), (190, 190, 200), "midbottom")
