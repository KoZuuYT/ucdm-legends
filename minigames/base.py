"""Base de todos os mini-games de treino.

Um treino novo = uma subclasse com `key` (entrada em minigames.json) e os
métodos `spawn`, `step_objects`, `handle_input`, `draw_objects`. Tudo o resto
(contagem, vidas, combo, HUD, recompensa, save, tela de resultado) é herdado.
Registre com @register para aparecer automaticamente no hub.
"""
import random

import pygame

from core import config, ui
from core.input import VirtualButton
from core.scene import Scene
from entities import roster
from systems import backdrop
from systems.particles import ParticleSystem
from systems.pool import Pool

REGISTRY: dict[str, type["TrainingGame"]] = {}


def register(cls):
    REGISTRY[cls.key] = cls
    return cls


class Obj:
    """Objeto genérico de mini-game (alvo, projétil, obstáculo). Reaproveitado via Pool."""
    __slots__ = ("x", "y", "vx", "vy", "kind", "dir", "t", "life", "r", "done")

    def reset(self, **kw) -> "Obj":
        self.x = self.y = self.vx = self.vy = self.t = self.life = 0.0
        self.r = 30.0
        self.kind, self.dir, self.done = "normal", "left", False
        for k, v in kw.items():
            setattr(self, k, v)
        return self


class TrainingGame(Scene):
    key = "base"
    theme = "meadow"
    PLAYER_POS = (640, 560)
    PLAYER_H = 200
    COUNTDOWN = 2.5

    def __init__(self, game) -> None:
        super().__init__(game)
        self.cfg = config.load("minigames")[self.key]
        self.stat = self.cfg["stat"]
        self.level = game.profile.level(self.stat)
        self.lives = self.cfg.get("lives", 3)
        self.duration = self.cfg["duration"]
        self.score = self.combo = self.best_combo = 0
        self.elapsed = 0.0
        self.countdown = self.COUNTDOWN
        self.spawn_timer = 0.5
        self.finished = False
        self.objs: Pool[Obj] = Pool(Obj, 48)
        self.fx = ParticleSystem(400)
        self.shake = 0.0
        self.font = game.assets.font(30)
        self.small = game.assets.font(20)
        self.big = game.assets.font(72)
        self.char = roster.character(game.profile.character)
        self.player_flip = self.char.get("faces", -1) != 1

    # --- utilitários de dificuldade ----------------------------------------------
    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    def ramp(self, key: str, level_scaled: bool = False) -> float:
        a, b = self.cfg[key]
        v = a + (b - a) * self.progress
        if level_scaled:   # mais nível = treino um pouco mais rápido (e mais XP)
            v *= 1 + 0.02 * (self.level - 1)
        return v

    @property
    def multiplier(self) -> int:
        return min(4, 1 + self.combo // 10)

    # --- pontuação --------------------------------------------------------------------
    def add_points(self, base: int, x: float, y: float, label: str = "", color=ui.ACCENT) -> None:
        pts = base * self.multiplier
        self.score += pts
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.fx.burst(x, y, color, n=10, speed=220, gravity=500)
        self.fx.text(x, y - 30, self.small.render(f"{label} +{pts}".strip(), True, color))
        self.game.audio.play("hit")

    def fail(self, x: float, y: float, label: str = "ERROU") -> None:
        self.combo = 0
        self.lives -= 1
        self.shake = 0.25 if self.game.feedback.shake_power("hit") > 0 else 0.0
        self.fx.burst(x, y, ui.RED, n=16, speed=280)
        self.fx.text(x, y - 30, self.small.render(label, True, ui.RED))
        self.game.audio.play("miss")
        if self.lives <= 0:
            self.finish()

    # --- hooks para subclasses -----------------------------------------------------
    def spawn(self) -> None: ...
    def step_objects(self, dt: float) -> None: ...
    def handle_input(self) -> None: ...
    def draw_objects(self, surf: pygame.Surface) -> None: ...
    def draw_player(self, surf: pygame.Surface) -> None:
        img = self.game.assets.image_h(self.char["sprite"], self.PLAYER_H, self.player_flip)
        surf.blit(img, img.get_rect(midbottom=self.PLAYER_POS))

    def virtual_buttons(self) -> list[VirtualButton]:
        """Botões de toque padrão: as 4 direções."""
        s, m = 110, 20
        W, H = self.game.display.width, self.game.display.height
        return [
            VirtualButton("left", pygame.Rect(m, H - s - m, s, s), "<"),
            VirtualButton("right", pygame.Rect(W - s - m, H - s - m, s, s), ">"),
            VirtualButton("up", pygame.Rect(m, H - 2 * s - 2 * m, s, s), "^"),
            VirtualButton("down", pygame.Rect(W - s - m, H - 2 * s - 2 * m, s, s), "v"),
        ]

    # --- ciclo de vida -------------------------------------------------------------
    def enter(self) -> None:
        self.game.input.set_virtual_buttons(self.virtual_buttons())
        self.game.audio.music("training")

    def exit(self) -> None:
        self.game.input.set_virtual_buttons([])
        self.objs.clear()
        self.fx.clear()

    def update(self, dt: float) -> None:
        inp = self.game.input
        self.fx.update(dt)
        self.shake = max(0.0, self.shake - dt)
        if self.finished:
            return
        if inp.pressed("back"):
            self._pause()
            return
        if self.countdown > 0:
            self.countdown -= dt
            return
        self.elapsed += dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn()
            self.spawn_timer = self.ramp("spawn_interval") * random.uniform(0.8, 1.2)
        self.handle_input()
        self.step_objects(dt)
        self.objs.release_where(lambda o: o.done)
        if self.elapsed >= self.duration and not self.finished:
            self.finish()

    def on_focus_lost(self) -> None:
        if not self.finished and self.game.scenes.current is self:
            self._pause()

    def _pause(self) -> None:
        from scenes.pause import PauseOverlay
        self.game.audio.play("pause")
        self.game.scenes.push(PauseOverlay(self.game, on_quit=lambda: self.game.scenes.pop(fade=True)))

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        prof = self.game.profile
        prof.bump("trainings")
        bonus = 1 + 0.05 * (self.level - 1)
        xp = int(self.score * self.cfg["xp_per_point"] * bonus)
        gold = int(self.score * self.cfg["gold_per_point"])
        levels = prof.stats[self.stat].add_xp(xp)
        prof.gold += gold
        best = prof.best_scores.get(self.key, 0)
        record = self.score > best
        if record:
            prof.best_scores[self.key] = self.score
        self.game.save.save(prof)
        label = config.load("balance")["stats"][self.stat]["label"]
        lines = [f"Pontos: {self.score}" + ("   NOVO RECORDE!" if record else f"   (recorde {best})"),
                 f"Maior combo: {self.best_combo}",
                 f"+{xp} XP de {label}", f"+{gold} ouro"]
        if levels:
            lines.append(f"{label} subiu para o nível {prof.level(self.stat)}!")
            self.game.audio.play("levelup")
        from scenes.results import ResultsOverlay
        self.game.scenes.push(ResultsOverlay(self.game, self.cfg["title"], lines,
                                             on_close=lambda: self.game.scenes.pop(fade=True)))

    # --- render ----------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        target = surf
        if self.shake > 0:   # desenha num buffer reaproveitado e o desloca (tremor de tela)
            if getattr(self, "_buf", None) is None or self._buf.get_size() != (W, H):
                self._buf = pygame.Surface((W, H))
            surf = self._buf
        surf.blit(backdrop.build(self.theme, (W, H), self.PLAYER_POS[1], self.game.assets), (0, 0))
        self.draw_player(surf)
        self.draw_objects(surf)
        self.fx.draw(surf)
        if surf is not target:
            target.blit(surf, (random.randint(-8, 8), random.randint(-8, 8)))
            surf = target
        self.draw_hud(surf)
        self.game.input.draw_virtual_buttons(surf, self.font)

    def draw_hud(self, surf: pygame.Surface) -> None:
        W = surf.get_width()
        ui.text(surf, self.font, self.cfg["title"], (W // 2, 14), anchor="midtop")
        ui.bar(surf, (W // 2 - 200, 56, 400, 16), 1 - self.progress, ui.BLUE)
        ui.text(surf, self.font, f"{self.score}", (24, 16))
        ui.text(surf, self.small, f"combo {self.combo}  x{self.multiplier}", (24, 54), ui.ACCENT)
        for i in range(self.lives):
            pygame.draw.circle(surf, ui.RED, (W - 40 - i * 34, 32), 13)
            pygame.draw.circle(surf, ui.WHITE, (W - 40 - i * 34, 32), 13, 2)
        ui.text(surf, self.small, f"Nível {self.level}", (W - 24, 54), anchor="topright")
        if self.countdown > 0:
            n = int(self.countdown) + 1
            ui.text(surf, self.big, str(n) if self.countdown > 0.4 else "JÁ!", (W // 2, 260), ui.ACCENT, "center")
            ui.text(surf, self.small, self.hint(), (W // 2, 330), anchor="center")

    def hint(self) -> str:
        return ""
