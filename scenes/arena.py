"""Arena de combate em tempo real.

Controles: mover (esq/dir), atacar (J/Z), bloquear segurando (K/X),
esquivar (L/C/Shift). Bloquear no instante do golpe = PARRY (atordoa).
Avisos vermelhos (!!) são imbloqueáveis: esquive!

O cenário é largo e cheio de decoração/plateia; tudo passa pelo SpatialGrid
e só o que a câmera enxerga é desenhado (veja F3 -> "decoração desenhada").
"""
import dataclasses
import math
import random

import pygame

from core import config, ui
from core.i18n import tr
from core.input import VirtualButton
from core.scene import Scene
from entities import roster
from entities.ai import EnemyBrain
from systems import backdrop
from systems.culling import Camera, SpatialGrid
from systems.tween import ease_in_out_sine
from systems.particles import ParticleSystem

WORLD_W, GROUND_Y = 3200, 600
BOUNDS = (260.0, WORLD_W - 260.0)


class Decor:
    __slots__ = ("kind", "x", "y", "h", "sprite", "rect", "parallax", "color")

    def __init__(self, kind, x, y, h, sprite=None, color=(0, 0, 0)):
        self.kind, self.x, self.y, self.h, self.sprite, self.color = kind, x, y, h, sprite, color
        self.rect = pygame.FRect(x - h, y - h, h * 2, h)


class ArenaScene(Scene):
    def __init__(self, game, stage: int) -> None:
        super().__init__(game)
        self.stage = stage
        self.edef = roster.enemies()[stage]
        mid = WORLD_W / 2
        self.player = roster.build_player(game.profile, mid - 220, GROUND_Y)
        self.enemy = roster.build_enemy(self.edef, mid + 220, GROUND_Y)
        self._apply_gameplay_options()
        self.brain = EnemyBrain(self.enemy, self.player, self.edef.get("ai", {}))
        W, H = game.display.width, game.display.height
        self.camera = Camera(W, H, pygame.Rect(0, -200, WORLD_W, H + 200))
        self.camera.view.center = (mid, GROUND_Y - 260)
        self.fx = ParticleSystem(500)
        self.fx.scale = 0.0 if game.feedback.intensity <= 0 else min(1.5, game.feedback.intensity)
        if game.low_perf:
            self.fx.scale *= 0.4
            self.player.ghosts_on = self.enemy.ghosts_on = False
        self.scenery = backdrop.Scenery(game, "arena", GROUND_Y, ambient=True)
        self._buf: pygame.Surface | None = None
        self._zoom_focus = (0.5, 0.6)
        self.fb = game.feedback
        self.big_font = game.assets.font(46)
        self.ghost_p = self.ghost_e = 1.0       # barras "fantasma" de vida (escorrem após o dano)
        self._warned = False
        self._vignette: pygame.Surface | None = None
        self.font = game.assets.font(26)
        self.small = game.assets.font(18)
        self.dmg_font = game.assets.font(34)
        self.now = 0.0
        self.over = 0.0          # tempo desde o fim da luta
        self.result: str | None = None
        self.parry_stun = config.load("balance")["fighter"]["parry_stun"]
        self.decor = SpatialGrid[Decor](cell=256)
        self.decor_drawn = 0
        self._dark_cache: dict = {}
        self._build_world()

    # --- mundo --------------------------------------------------------------------------
    def _build_world(self) -> None:
        rnd = random.Random(self.stage)
        chars = roster.characters()
        # plateia: personagens UCDM em silhueta ao fundo
        for x in range(0, WORLD_W, 110):
            c = rnd.choice(chars)
            d = Decor("crowd", x + rnd.uniform(-20, 20), GROUND_Y - 175 + rnd.uniform(-8, 8), rnd.randint(70, 95),
                      sprite=c["sprite"])
            self.decor.insert(d, d.rect)
        for _ in range(60):
            x = rnd.uniform(0, WORLD_W)
            kind = rnd.choice(("rock", "flag", "torch"))
            h = {"rock": rnd.randint(20, 40), "flag": rnd.randint(140, 190), "torch": 110}[kind]
            col = rnd.choice([(200, 60, 60), (60, 120, 220), (230, 190, 60), (90, 180, 90)])
            d = Decor(kind, x, GROUND_Y - 120 if kind != "rock" else GROUND_Y + rnd.uniform(20, 100), h, color=col)
            self.decor.insert(d, d.rect)

    def _dark(self, sprite: str, h: int) -> pygame.Surface:
        key = (sprite, h)
        s = self._dark_cache.get(key)
        if s is None:
            s = self.game.assets.image_h(sprite, h).copy()
            s.fill((70, 62, 85), special_flags=pygame.BLEND_RGB_MULT)
            self._dark_cache[key] = s
        return s

    def _apply_gameplay_options(self) -> None:
        """Dificuldade e aviso estendido (Opções -> Jogo). Só mexem em números, nunca nas regras."""
        gp = self.game.cfg.get("gameplay", {})
        enemy_dmg, parry = {"easy": (0.75, 1.25), "hard": (1.25, 0.85)}.get(gp.get("difficulty", "normal"), (1.0, 1.0))
        self.enemy.damage *= enemy_dmg
        self.player.parry_window *= parry
        if gp.get("extended_warning"):
            self.enemy.attacks = [dataclasses.replace(a, windup=a.windup * 1.5) if a.unblockable else a
                                  for a in self.enemy.attacks]

    # --- ciclo de vida ------------------------------------------------------------------
    def on_focus_lost(self) -> None:
        if self.result is None and self.game.scenes.current is self:
            self._pause()

    def _pause(self) -> None:
        from scenes.pause import PauseOverlay
        self.game.audio.play("pause")
        self.game.scenes.push(PauseOverlay(self.game, on_quit=lambda: self.game.scenes.pop(fade="iris")))

    def enter(self) -> None:
        self.game.audio.music("arena")
        W, H = self.game.display.width, self.game.display.height
        s, m = 100, 18
        self.game.input.set_virtual_buttons([
            VirtualButton("left", pygame.Rect(m, H - s - m, s, s), "<"),
            VirtualButton("right", pygame.Rect(m * 2 + s, H - s - m, s, s), ">"),
            VirtualButton("block", pygame.Rect(W - 3 * (s + m), H - s - m, s, s), "DEF"),
            VirtualButton("dodge", pygame.Rect(W - 2 * (s + m), H - s - m, s, s), "ESQ"),
            VirtualButton("attack", pygame.Rect(W - (s + m), H - s - m - 60, s, s + 60), "ATK"),
        ])

    def exit(self) -> None:
        self.game.input.set_virtual_buttons([])
        self.fx.clear()

    # --- lógica -------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.now += dt
        inp = self.game.input
        p, e = self.player, self.enemy
        if inp.pressed("back") and self.result is None:
            self._pause()
            return

        if self.result is None and p.state != "dead":
            p.facing = 1 if e.pos.x > p.pos.x else -1
            if inp.pressed("dodge"):
                p.dodge()
            if inp.pressed("attack"):
                p.attack_cmd()
            p.set_block(inp.held("block"), self.now)
            mv = (1 if inp.held("right") else 0) - (1 if inp.held("left") else 0)
            if mv and p.state != "block":
                p.move(mv)
        self.brain.update(dt, self.now)
        p.update(dt, BOUNDS)
        e.update(dt, BOUNDS)
        self._separate()
        for att, dfn in ((p, e), (e, p)):
            if att.pending_hit:
                self._resolve(att, dfn)
        self._warning_cues(e)
        self.ghost_p = max(p.hp / p.max_hp, self.ghost_p - 0.45 * dt)
        self.ghost_e = max(e.hp / e.max_hp, self.ghost_e - 0.45 * dt)
        self.fx.update(dt)
        self.camera.follow((p.pos.x + e.pos.x) / 2, GROUND_Y - 260, dt)
        self.camera.update(dt)

        if self.result is None and (p.state == "dead" or e.state == "dead"):
            self.result = "win" if e.state == "dead" else "lose"
            ko = e if self.result == "win" else p
            x, y = ko.pos.x, ko.pos.y - ko.height * 0.5
            self.fx.burst(x, y, (255, 240, 200), n=34, speed=420, size=6)
            self.fx.ring(x, y, (255, 240, 200), radius=260, life=0.6, width=8)
            self.fb.ko()
            self.fb.flash((255, 255, 255), 0.55)
            self.camera.shake(self.fb.shake_power("ko"), 0.35)
            self.game.audio.play("ko")
            self.game.audio.duck(1.4)
            self.game.profile.bump("fights")
            if self.result == "lose":
                self.game.profile.bump("losses")
        if self.result:
            self.over += dt
            if self.over >= 1.4 and self.game.scenes.current is self:
                self._finish()

    def _separate(self) -> None:
        p, e = self.player, self.enemy
        min_gap = 150
        gap = e.pos.x - p.pos.x
        if abs(gap) < min_gap and "dodge" not in (p.state, e.state):
            push = (min_gap - abs(gap)) / 2 * (1 if gap >= 0 else -1)
            p.pos.x -= push
            e.pos.x += push

    def _warning_cues(self, e) -> None:
        """Golpe imbloqueável (!!) do inimigo: som de alerta uma vez por golpe."""
        danger = e.state == "windup" and e.attack is not None and e.attack.unblockable
        if danger and not self._warned:
            self.game.audio.play("warning")
            self.fb.flash((255, 60, 50), 0.22)
        self._warned = danger

    def _resolve(self, att, dfn) -> None:
        atk, att.pending_hit = att.pending_hit, None
        if abs(dfn.pos.x - att.pos.x) > att.reach + 20:
            return
        res = dfn.receive(atk, att, self.now)
        x, y = dfn.pos.x, dfn.pos.y - dfn.height * 0.6
        audio, fb, prof = self.game.audio, self.fb, self.game.profile
        mine = dfn is self.player           # o jogador é quem está se defendendo
        if res.outcome == "parry":
            att.stun(self.parry_stun)
            self.fx.burst(x, y, ui.ACCENT, n=24, speed=360)
            self.fx.ring(x, y, (150, 220, 255), radius=170, life=0.4, width=7)
            self._float(x, y, "PARRY!", ui.ACCENT, self.big_font)
            self.camera.shake(fb.shake_power("parry"))
            fb.hitstop("parry")
            fb.flash((150, 220, 255), 0.3)
            audio.play("parry")
            audio.duck(0.5)
            if mine:
                prof.bump("parries")
        elif res.outcome == "dodge":
            self._float(x, y, "ESQUIVA", ui.GREEN)
            audio.play("whoosh")
            if mine:
                prof.bump("dodges")
        elif res.outcome == "block":
            self.fx.burst(x, y, ui.BLUE, n=8)
            self._float(x, y, f"-{res.damage}", ui.BLUE)
            audio.play("block")
            fb.hitstop("hit")
        elif res.outcome in ("hit", "crit"):
            crit = res.outcome == "crit"
            self.fx.burst(x, y, (255, 230, 120) if crit else (230, 60, 50), n=20 if crit else 12)
            if crit:
                self.fx.ring(x, y, (255, 215, 90), radius=140, life=0.35, width=6)
                fb.flash((255, 215, 90), 0.25)
            self._float(x, y, f"-{res.damage}" + (" CRÍTICO" if crit else ""), ui.ACCENT if crit else ui.RED,
                        self.big_font if crit else None)
            self.camera.shake(fb.shake_power("crit" if crit else "hit"))
            fb.hitstop("crit" if crit else "hit")
            audio.play("crit" if crit else "hit")
            if not mine:
                prof.bump("hits_landed")
                prof.bump("damage_dealt", res.damage)
                prof.record("max_hit", res.damage)
                if crit:
                    prof.bump("crits")

    def _float(self, x, y, msg, color, font=None) -> None:
        self.fx.text(x, y, (font or self.dmg_font).render(tr(msg), True, color))

    def _finish(self) -> None:
        prof = self.game.profile
        from scenes.results import ResultsOverlay
        if self.result == "win":
            gold = self.edef.get("gold", 20)
            first = self.stage == prof.arena_stage
            if not first:
                gold //= 3   # revanche rende menos
            prof.gold += gold
            prof.wins += 1
            prof.bump("fights_won")
            if first:
                prof.arena_stage += 1
            lines = [f"Você derrotou {self.enemy.name}!", f"+{gold} ouro"]
            if first and prof.arena_stage < len(roster.enemies()):
                nxt = roster.character(roster.enemies()[prof.arena_stage]["character"])["name"]
                lines.append(f"Próximo desafiante: {nxt}")
            self.game.audio.play("coin")
            title, color = "VITÓRIA", ui.ACCENT
        else:
            lines = [f"{self.enemy.name} venceu desta vez.", "Treine seus atributos e volte!"]
            title, color = "DERROTA", ui.RED
        self.game.save.save(prof)
        self.game.scenes.push(ResultsOverlay(self.game, title, lines,
                                             on_close=lambda: self.game.scenes.pop(fade=True), color=color))

    # --- render -------------------------------------------------------------------------
    def _zoom(self) -> float:
        """Zoom do mundo (não do HUD): leve aproximação no KO que volta ao normal."""
        if self.result is None or self.fb.reduce_motion or self.fb.intensity <= 0 or self.game.low_perf:
            return 1.0
        return 1.0 + 0.08 * min(1.0, self.fb.intensity) * math.sin(math.pi * ease_in_out_sine(min(1.0, self.over / 1.4)))

    def draw(self, surf: pygame.Surface) -> None:
        z = self._zoom()
        if z > 1.003:
            W, H = surf.get_size()
            if self._buf is None or self._buf.get_size() != (W, H):
                self._buf = pygame.Surface((W, H))
            self._draw_world(self._buf)
            ko = self.enemy if self.result == "win" else self.player
            fx, fy = self.camera.to_screen(ko.pos.x, ko.pos.y - ko.height * 0.5)
            cw, ch = int(W / z), int(H / z)
            crop = pygame.Rect(0, 0, cw, ch)
            crop.center = (int(fx), int(fy))
            crop.clamp_ip(self._buf.get_rect())
            pygame.transform.smoothscale(self._buf.subsurface(crop), (W, H), surf)
        else:
            self._draw_world(surf)
        self._hud(surf)
        self.game.input.draw_virtual_buttons(surf, self.font)

    def _draw_world(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        cam = self.camera
        # fundo com parallax barato: 1 blit de superfície cacheada
        bg = backdrop.build("arena", (W + 400, H), GROUND_Y - 40, self.game.assets)
        surf.blit(bg, (-max(0.0, min(400.0, cam.view.x * 0.2)), 0))
        self.scenery.draw_ambient(surf, self.now, cam.view.x)
        gy = cam.to_screen(0, GROUND_Y)[1]
        surf.fill((175, 150, 110), (0, gy - 40, W, H))
        pygame.draw.line(surf, (130, 105, 75), (0, gy - 40), (W, gy - 40), 4)

        # decoração: consulta só o que está no viewport
        visible = self.decor.query(cam.view.inflate(200, 200))
        visible.sort(key=lambda d: d.y)
        self.decor_drawn = len(visible)
        for d in visible:
            x, y = cam.to_screen(d.x, d.y)
            if d.kind == "crowd":
                img = self._dark(d.sprite, d.h)
                surf.blit(img, img.get_rect(midbottom=(x, y + d.h)))
            elif d.kind == "flag":
                pygame.draw.line(surf, (80, 60, 40), (x, y), (x, y - d.h), 5)
                pygame.draw.polygon(surf, d.color, [(x, y - d.h), (x + 50, y - d.h + 18), (x, y - d.h + 36)])
            elif d.kind == "torch":
                pygame.draw.line(surf, (70, 50, 35), (x, y), (x, y - d.h), 7)
                r = 10 + int(3 * ((self.now * 9 + d.x) % 2))
                pygame.draw.circle(surf, (255, 170, 60), (int(x), int(y - d.h - 8)), r)
            else:
                pygame.draw.ellipse(surf, (140, 120, 95), (x - d.h, y - d.h / 2, d.h * 2, d.h))

        for f in sorted((self.player, self.enemy), key=lambda f: f.state == "strike"):
            f.draw(surf, cam, self.game.assets, self.font)
        self.fx.draw(surf, cam)

    def _danger_vignette(self, surf: pygame.Surface) -> None:
        """Borda vermelha pulsando enquanto o inimigo prepara um golpe imbloqueável (máx. ~1,5 Hz)."""
        e = self.enemy
        if not (e.state == "windup" and e.attack is not None and e.attack.unblockable) or self.fb.intensity <= 0 \
                or self.game.low_perf:
            return
        W, H = surf.get_size()
        if self._vignette is None or self._vignette.get_size() != (W, H):
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(46):
                pygame.draw.rect(v, (255, 40, 30, int(150 * (1 - i / 46) ** 2)), (i, i, W - 2 * i, H - 2 * i), 1)
            self._vignette = v
        pulse = 0.75 if self.fb.reduce_motion else 0.55 + 0.45 * math.sin(self.now * math.tau * 1.5)
        self._vignette.set_alpha(int(255 * max(0.2, min(1.0, pulse * min(1.0, self.fb.intensity)))))
        surf.blit(self._vignette, (0, 0))

    def _hud(self, surf: pygame.Surface) -> None:
        W = surf.get_width()
        p, e = self.player, self.enemy
        self._danger_vignette(surf)
        ui.text(surf, self.font, p.name, (24, 16))
        ui.bar(surf, (24, 48, 420, 22), p.hp / p.max_hp, ui.RED, ghost=self.ghost_p)
        ui.text(surf, self.small, f"{int(p.hp)}/{int(p.max_hp)}", (234, 50), anchor="midtop")
        low = p.stamina < p.dodge_cost
        sta_col = (255, 150, 50) if low and int(self.now * 6) % 2 == 0 else ui.GREEN
        ui.bar(surf, (24, 76, 300, 12), p.stamina / p.max_stamina, sta_col)
        ui.text(surf, self.font, e.name, (W - 24, 16), anchor="topright")
        ui.bar(surf, (W - 444, 48, 420, 22), e.hp / e.max_hp, ui.RED, ghost=self.ghost_e)
        ui.text(surf, self.small, self.edef.get("title", ""), (W - 24, 76), ui.ACCENT, "topright")
        if not self.game.input.touch_mode and self.now < 6:
            ui.text(surf, self.small, "Mover: setas/AD   Atacar: J   Defender: K (segure)   Esquivar: L / Shift   Pausa: Esc",
                    (W // 2, 110), anchor="midtop")

    def debug_info(self) -> str:
        return f"Decoração desenhada {self.decor_drawn}/{len(self.decor)}"
