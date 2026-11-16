"""Arena de combate em tempo real.

Controles padrão: mover (A/D ou setas), atacar (botão esquerdo do mouse / J), defender segurando (F / K),
esquivar (Shift / L). Bloquear no instante exato = PARRY (atordoa). Esquivar no último instante = ESQUIVA PERFEITA.
Os dois abrem um CONTRA-ATAQUE (crítico garantido). Avisos: vermelho (!!) = imbloqueável, esquive;
laranja = quebra a guarda, aparar ou esquive. Atacar sem parar causa FADIGA e o inimigo aprende a se defender.

A luta começa com uma entrada animada (lutadores deslizam, tela de versus e contagem 3-2-1).
O cenário é largo e cheio de decoração/plateia; tudo passa pelo SpatialGrid
e só o que a câmera enxerga é desenhado (veja F3 -> "decoração desenhada").
"""
import dataclasses
import math
import random

import pygame

from core import compat

from core import config, mcui, theme, ui
from core import mcassets as mc
from core.i18n import tr
from core.input import VirtualButton, pretty_key
from core.scene import Scene
from systems import achievements, grading
from entities import roster
from entities.ai import EnemyBrain
from systems import backdrop
from systems.culling import Camera, SpatialGrid
from systems.particles import ParticleSystem
from systems.tween import ease_in_out_sine, ease_out_back, ease_out_cubic

WORLD_W, GROUND_Y = 3200, 600
BOUNDS = (260.0, WORLD_W - 260.0)
INTRO_VS_START, INTRO_COUNT_START, INTRO_TOTAL = 0.9, 2.5, 4.0     # s: entrada, "VS", contagem, fim


class Decor:
    __slots__ = ("kind", "x", "y", "h", "sprite", "rect", "parallax", "color", "flip")

    def __init__(self, kind, x, y, h, sprite=None, color=(0, 0, 0), flip=False):
        self.kind, self.x, self.y, self.h, self.sprite, self.color, self.flip = kind, x, y, h, sprite, color, flip
        self.rect = compat.FRect(x - h, y - h, h * 2, h)


class ArenaScene(Scene):
    wide = True

    def __init__(self, game, stage: int, challenger: str | None = None, endless: int = 0,
                 daily: dict | None = None) -> None:
        super().__init__(game)
        self.daily = daily                               # modificador do Desafio do Dia (ou None)
        self.challenger = challenger                     # id de uma lenda do álbum (desafio fora da escada)
        self.endless = endless                           # >0: onda atual da Arena Infinita
        self.stage = stage if challenger is None else -1
        if endless:
            self.edef = roster.endless_edef(endless, challenger)
        else:
            self.edef = roster.challenge_edef(challenger) if challenger else roster.enemies()[stage]
        mid = WORLD_W / 2
        self.mid = mid
        self.player = roster.build_player(game.profile, mid - 220, GROUND_Y)
        self.enemy = roster.build_enemy(self.edef, mid + 220, GROUND_Y)
        self._apply_gameplay_options()
        if daily:
            self._apply_daily(daily)
        self.brain = EnemyBrain(self.enemy, self.player, self.edef.get("ai", {}))
        W, H = game.display.canvas_w, game.display.height
        self.camera = Camera(W, H, pygame.Rect(0, -200, WORLD_W, H + 200))
        self.camera.view.center = (mid, GROUND_Y - 260)
        self.fx = ParticleSystem(500)
        self.fx.scale = 0.0 if game.feedback.intensity <= 0 else min(1.5, game.feedback.intensity)
        if game.low_perf:
            self.fx.scale *= 0.4
            self.player.ghosts_on = self.enemy.ghosts_on = False
        self.scenery = backdrop.Scenery(game, "arena", GROUND_Y, ambient=True)
        self._buf: pygame.Surface | None = None
        self.fb = game.feedback
        self.big_font = game.assets.font(46)
        self.font = game.assets.font(26)
        self.small = game.assets.font(18)
        self.dmg_font = game.assets.font(34)
        self.ghost_p = self.ghost_e = 1.0       # barras "fantasma" de vida (escorrem após o dano)
        self.hurt_flash = 0.0                   # borda vermelha quando o jogador leva dano
        self.hud_shake = 0.0
        self.style_total = 0                    # esquivas perfeitas + parries (bônus de ouro no fim)
        self.st = dict(taken=0, dealt=0, parries=0, perfect_dodges=0, dodges=0, breaks=0, guardbreaks_taken=0,
                       unblockable_taken=0, attacks=0, hits_landed=0, fatigue_peak=0.0)
        self._tired_cd = 0.0
        self._warned = False
        self._vignette: pygame.Surface | None = None
        self.now = 0.0
        self._counted_windup = False
        self.over = 0.0          # tempo desde o fim da luta
        self.result: str | None = None
        self.parry_stun = config.load("balance")["fighter"]["parry_stun"]
        self.decor = SpatialGrid[Decor](cell=256)
        self.decor_drawn = 0
        self._dark_cache: dict = {}
        self._build_world()
        # --- entrada animada ---
        self.intro = 0.0
        self._intro_events: set[str] = set()
        self._start_x = (mid - 220, mid + 220)
        if self._intro_enabled():
            self.player.pos.x, self.enemy.pos.x = mid - 220 - 520, mid + 220 + 520
        else:
            self.intro = INTRO_TOTAL

    # --- mundo --------------------------------------------------------------------------
    def _build_world(self) -> None:
        rnd = random.Random(self.challenger or self.stage)
        chars = roster.characters()
        # plateia: personagens UCDM em silhueta ao fundo, virados para o centro da arena
        for x in range(0, WORLD_W, 110):
            c = rnd.choice(chars)
            look = 1 if x < WORLD_W / 2 else -1
            d = Decor("crowd", x + rnd.uniform(-20, 20), GROUND_Y - 175 + rnd.uniform(-8, 8), rnd.randint(70, 95),
                      sprite=c["sprite"], flip=look != c.get("faces", -1))
            self.decor.insert(d, d.rect)
        for _ in range(60):
            x = rnd.uniform(0, WORLD_W)
            kind = rnd.choice(("rock", "flag", "torch"))
            h = {"rock": rnd.randint(20, 40), "flag": rnd.randint(140, 190), "torch": 110}[kind]
            col = rnd.choice([(200, 60, 60), (60, 120, 220), (230, 190, 60), (90, 180, 90)])
            d = Decor(kind, x, GROUND_Y - 120 if kind != "rock" else GROUND_Y + rnd.uniform(20, 100), h, color=col)
            self.decor.insert(d, d.rect)

    def _dark(self, sprite: str, h: int, flip: bool) -> pygame.Surface:
        key = (sprite, h, flip)
        s = self._dark_cache.get(key)
        if s is None:
            s = self.game.assets.image_h(sprite, h, flip).copy()
            s.fill((70, 62, 85), special_flags=pygame.BLEND_RGB_MULT)
            self._dark_cache[key] = s
        return s

    def _apply_gameplay_options(self) -> None:
        """Dificuldade e aviso estendido (Opções -> Jogo). Só mexem em números, nunca nas regras."""
        gp = self.game.cfg.get("gameplay", {})
        enemy_dmg, parry = {"easy": (0.75, 1.25), "hard": (1.25, 0.85)}.get(gp.get("difficulty", "normal"), (1.0, 1.0))
        self.enemy.damage *= enemy_dmg
        self.player.parry_window *= parry
        self.enemy.timing_aid = bool(gp.get("timing_aid", True))
        if gp.get("extended_warning"):
            self.enemy.attacks = [dataclasses.replace(a, windup=a.windup * 1.5) if (a.unblockable or a.guard_break) else a
                                  for a in self.enemy.attacks]

    def _apply_daily(self, m: dict) -> None:
        p, e = self.player, self.enemy
        if m.get("player_hp"):
            p.hp = p.max_hp * m["player_hp"]
        if m.get("enemy_hp"):
            e.max_hp = e.hp = e.max_hp * m["enemy_hp"]
        if m.get("enemy_damage"):
            e.damage *= m["enemy_damage"]
        if m.get("enemy_poise"):
            e.max_poise = e.poise = e.max_poise * m["enemy_poise"]
        if m.get("enemy_windup"):
            e.attacks = [dataclasses.replace(a, windup=a.windup * m["enemy_windup"]) for a in e.attacks]

    def _intro_enabled(self) -> bool:
        return not self.game.headless and self.game.cfg.get("gameplay", {}).get("battle_intro", True)

    # --- ciclo de vida ------------------------------------------------------------------
    def on_focus_lost(self) -> None:
        if self.result is None and self.game.scenes.current is self:
            self._pause()

    def _pause(self) -> None:
        from scenes.pause import PauseOverlay
        self.game.audio.play("pause")
        p, e = self.player, self.enemy
        info = [f"{self.enemy.name}  ·  {tr('Vida')}: {int(p.hp)}/{int(p.max_hp)} × {int(e.hp)}/{int(e.max_hp)}",
                f"{tr('Tempo')}: {int(self.now // 60)}:{int(self.now % 60):02d}"]
        self.game.scenes.push(PauseOverlay(self.game, on_quit=lambda: self.game.scenes.pop(fade="iris"),
                                           on_restart=self._restart, info=info))

    def on_resize(self, canvas_w: int) -> None:
        self.camera.view.w = canvas_w
        self._vignette = self._buf = None
        if self.game.scenes.current is self:
            self._set_touch_buttons()

    def enter(self) -> None:
        self.game.audio.music("arena")
        self._set_touch_buttons()

    def _set_touch_buttons(self) -> None:
        W, H = self.game.display.canvas_w, self.game.display.height
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

    # --- entrada animada --------------------------------------------------------------------
    @property
    def in_intro(self) -> bool:
        return self.intro < INTRO_TOTAL

    def _update_intro(self, dt: float) -> None:
        a = self.game.audio
        p, e = self.player, self.enemy
        prev = self.intro
        self.intro += dt
        t = self.intro
        k = ease_out_cubic(min(1.0, t / INTRO_VS_START))              # lutadores deslizam para a posição
        p.pos.x = self._start_x[0] - 520 * (1 - k)
        e.pos.x = self._start_x[1] + 520 * (1 - k)
        for f in (p, e):
            f.state, f.timer = ("walk" if k < 0.999 else "idle"), 0.0
            f._move = 0
            f.anim_t += dt
        if "whoosh" not in self._intro_events:
            self._intro_events.add("whoosh")
            a.play("whoosh")
        if t >= INTRO_VS_START and "land" not in self._intro_events:
            self._intro_events.add("land")
            for f in (p, e):
                f.spawn_t = 0.45
                self.fx.puff(f.pos.x, f.pos.y - 4, (210, 195, 160), n=7, size=22)
            self.camera.shake(self.fb.shake_power("hit"), 0.25)
            a.play("hit1")
        if t >= INTRO_VS_START + 0.25 and "vs" not in self._intro_events:
            self._intro_events.add("vs")
            self.fb.flash((255, 255, 255), 0.35)
            a.play("crit1")
        for n, label in enumerate(("3", "2", "1")):
            if t >= INTRO_COUNT_START + n * 0.4 and f"c{label}" not in self._intro_events:
                self._intro_events.add(f"c{label}")
                a.play("click1")
        go = INTRO_COUNT_START + 3 * 0.4
        if t >= go and "go" not in self._intro_events:
            self._intro_events.add("go")
            self.fb.flash((255, 215, 90), 0.4)
            self.camera.shake(self.fb.shake_power("crit"), 0.2)
            self.fx.ring(p.pos.x, p.pos.y - 100, (255, 215, 90), radius=220, life=0.5, width=8)
            self.fx.ring(e.pos.x, e.pos.y - 100, (255, 215, 90), radius=220, life=0.5, width=8)
            a.play("confirm1")
        if self.game.input.pressed("confirm") and prev > 0.7 or self.intro >= INTRO_TOTAL:
            self.intro = INTRO_TOTAL
            p.pos.x, e.pos.x = self._start_x
            p.state = e.state = "idle"
            p.spawn_t = e.spawn_t = 0.0
        self._drain_fx()
        self.fx.update(dt)
        self.camera.follow((p.pos.x + e.pos.x) / 2, GROUND_Y - 260, dt)
        self.camera.update(dt)
        for f in (p, e):
            f.spawn_t = max(0.0, f.spawn_t - dt)

    def _pop_text(self, surf, msg, base_size, scale, color, center) -> None:
        """Texto grande que "pula" (escala) sem criar uma fonte nova por tamanho."""
        font = self.game.assets.font(base_size)
        msg = tr(msg)
        w, h = font.size(msg)
        tmp = pygame.Surface((w + 28, h + 28), pygame.SRCALPHA)
        ui.text(tmp, font, msg, tmp.get_rect().center, color, "center")
        if abs(scale - 1) > 0.02:
            tmp = pygame.transform.smoothscale(tmp, (max(2, int(tmp.get_width() * scale)), max(2, int(tmp.get_height() * scale))))
        surf.blit(tmp, tmp.get_rect(center=center))

    def _draw_intro(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        t = self.intro
        a = self.game.assets
        p, e = self.player, self.enemy
        # faixa escura de "versus"
        if INTRO_VS_START - 0.2 <= t < INTRO_COUNT_START + 0.1:
            u = ease_out_cubic(min(1.0, (t - (INTRO_VS_START - 0.2)) / 0.3))
            out = ease_out_cubic(min(1.0, max(0.0, (t - (INTRO_COUNT_START - 0.25)) / 0.3)))
            band_h = int(210 * u * (1 - out))
            band = pygame.Surface((W, max(1, band_h)), pygame.SRCALPHA)
            band.fill((8, 10, 20, 205))
            surf.blit(band, (0, H // 2 - 90 - band_h // 2))
            line = int(W * u)
            pygame.draw.line(surf, ui.ACCENT, (W // 2 - line // 2, H // 2 - 90 - band_h // 2),
                             (W // 2 + line // 2, H // 2 - 90 - band_h // 2), 4)
            pygame.draw.line(surf, ui.ACCENT, (W // 2 - line // 2, H // 2 - 90 + band_h // 2),
                             (W // 2 + line // 2, H // 2 - 90 + band_h // 2), 4)
            if band_h > 150:
                for name, title, side in ((p.name, tr("Você"), -1), (e.name, self.edef.get("title", ""), 1)):
                    slide = 1 - ease_out_back(min(1.0, (t - INTRO_VS_START) / 0.45))
                    x = W // 2 + side * (230 + slide * 700)
                    anchor = "midright" if side < 0 else "midleft"
                    ui.text(surf, a.font(54), name, (x - side * 70, H // 2 - 110), ui.WHITE, anchor)
                    ui.text(surf, a.font(24), title, (x - side * 70, H // 2 - 60), ui.ACCENT, anchor)
                pop = ease_out_back(min(1.0, max(0.0, (t - INTRO_VS_START - 0.2) / 0.3)))
                self._pop_text(surf, "VS", 110, max(0.1, pop), ui.RED, (W // 2, H // 2 - 90))
        # contagem 3-2-1-LUTE
        if t >= INTRO_COUNT_START:
            n = int((t - INTRO_COUNT_START) / 0.4)
            local = ((t - INTRO_COUNT_START) % 0.4) / 0.4
            label = ("3", "2", "1", tr("LUTE!"))[min(3, n)]
            if n <= 3 and t < INTRO_COUNT_START + 3 * 0.4 + 0.55:
                sc = 0.7 + 0.5 * ease_out_back(min(1.0, local * 2.2))
                col = ui.ACCENT if n < 3 else ui.RED
                self._pop_text(surf, label, 100 if n < 3 else 120, sc, col, (W // 2, H // 2 - 80))
        if t > 0.8:
            ui.text(surf, a.font(16, bold=False), "Enter para pular", (W - 16, H - 12), (200, 200, 210), "bottomright")

    # --- lógica -------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.now += dt
        inp = self.game.input
        p, e = self.player, self.enemy
        if inp.pressed("back") and self.result is None:
            self._pause()
            return
        if self.in_intro:
            self._update_intro(dt)
            return

        self.hurt_flash = max(0.0, self.hurt_flash - dt * 2.2)
        self.hud_shake = max(0.0, self.hud_shake - dt * 3.0)
        self._tired_cd = max(0.0, self._tired_cd - dt)
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
        self.st["fatigue_peak"] = max(self.st["fatigue_peak"], p.fatigue)
        if p.state == "windup" and not self._counted_windup:
            self.st["attacks"] += 1
        self._counted_windup = p.state == "windup"
        if p.fatigue >= 3 and self._tired_cd <= 0 and p.state == "windup":
            self._tired_cd = 2.5
            self._float(p.pos.x, p.pos.y - p.height - 30, "CANSADO!", (240, 200, 90))
        self._drain_fx()
        self.ghost_p = max(p.hp / p.max_hp, self.ghost_p - 0.45 * dt)
        self.ghost_e = max(e.hp / e.max_hp, self.ghost_e - 0.45 * dt)
        self.fx.update(dt)
        self.camera.follow((p.pos.x + e.pos.x) / 2, GROUND_Y - 260, dt)
        self.camera.update(dt)

        if self.result is None and (p.state == "dead" or e.state == "dead"):
            self.result = "win" if e.state == "dead" else "lose"
            ko = e if self.result == "win" else p
            x, y = ko.pos.x, ko.pos.y - ko.height * 0.5
            self.fx.burst(x, y, (255, 240, 200), n=34, speed=420, size=6, streak=True)
            self.fx.ring(x, y, (255, 240, 200), radius=260, life=0.6, width=8)
            self.fx.star(x, y, (255, 240, 200), size=170, life=0.35)
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

    def _drain_fx(self) -> None:
        """Converte os pedidos de efeito dos lutadores (poeira, linhas de velocidade) em partículas."""
        for f in (self.player, self.enemy):
            for ev in f.fx_queue:
                kind, x, y = ev[0], ev[1], ev[2]
                if kind == "dust":
                    self.fx.puff(x, y - 4, (205, 190, 155), n=ev[3], size=16)
                elif kind == "lunge":
                    d = ev[3]
                    self.fx.burst(x - d * 50, y - f.height * 0.5, (255, 255, 255), n=7, speed=520, size=3, gravity=0,
                                  life=0.16, streak=True, direction=-d)
            f.fx_queue.clear()

    def _separate(self) -> None:
        p, e = self.player, self.enemy
        min_gap = 150
        gap = e.pos.x - p.pos.x
        if abs(gap) < min_gap and "dodge" not in (p.state, e.state):
            push = (min_gap - abs(gap)) / 2 * (1 if gap >= 0 else -1)
            p.pos.x -= push
            e.pos.x += push

    def _warning_cues(self, e) -> None:
        """Golpe especial do inimigo (!! vermelho ou laranja): som de alerta uma vez por golpe."""
        danger = e.state == "windup" and e.attack is not None and (e.attack.unblockable or e.attack.guard_break)
        if danger and not self._warned:
            self.game.audio.play("warning")
            self.fb.flash((255, 60, 50) if e.attack.unblockable else (255, 150, 40), 0.2)
        self._warned = danger

    # --- resolução de golpes ----------------------------------------------------------------
    def _mc_fx(self, kind: str, x: float, y: float, facing: int = 1) -> None:
        """Efeitos com os sprites de partícula do Minecraft (só no tema Minecraft)."""
        if not theme.mc() or ui.high_contrast or self.game.low_perf:
            return
        fx = self.fx
        if kind == "hit":
            fx.anim(x, y, "particle/sweep", 8, k=4, flip=facing < 0, tint=(255, 235, 225))
            fx.icons(x, y, "particle/damage.png", n=5, speed=300, k=4, direction=facing, tint=(235, 70, 55))
        elif kind == "crit":
            fx.anim(x, y, "particle/sweep", 8, k=6, flip=facing < 0, tint=(255, 225, 120))
            fx.icons(x, y, "particle/critical_hit.png", n=10, speed=420, k=5, direction=facing, tint=(255, 215, 90))
        elif kind == "parry":
            fx.icons(x, y, "particle/enchanted_hit.png", n=12, speed=380, k=5, tint=(150, 215, 255))
            fx.anim(x, y, "particle/spark", 8, k=7, fps=26, tint=(255, 215, 120))
        elif kind == "dodge":
            fx.anim(x, y, "particle/spark", 8, k=6, fps=28, tint=(140, 215, 255))
            fx.icons(x, y, "particle/glint.png", n=6, speed=260, k=4, gravity=0, tint=(190, 235, 255))
        elif kind == "break":
            fx.anim(x, y, "particle/explosion", 16, k=8, fps=36, tint=(255, 200, 110))
            fx.icons(x, y, "particle/critical_hit.png", n=8, speed=380, k=4, tint=(255, 215, 90))
        elif kind == "block":
            fx.icons(x, y, "particle/generic_3.png", n=5, speed=240, k=4, direction=facing, tint=(130, 170, 255))

    def _resolve(self, att, dfn) -> None:
        atk, att.pending_hit = att.pending_hit, None
        mine = dfn is self.player           # o jogador é quem está se defendendo
        x, y = dfn.pos.x, dfn.pos.y - dfn.height * 0.6
        if abs(dfn.pos.x - att.pos.x) > att.reach + 20:
            att.counter_time = 0.0
            if not mine:        # errou o golpe: fica exposto (castiga bater de longe sem pensar)
                att.stun(0.3)
                self._float(att.pos.x, att.pos.y - att.height - 20, "ERROU", (190, 190, 190))
            return
        res = dfn.receive(atk, att, self.now)
        audio, fb, prof, fx = self.game.audio, self.fb, self.game.profile, self.fx
        facing = att.facing
        if res.outcome == "parry":
            if mine and att.damage_poise(att.max_poise * 0.45):
                self._poise_broken(att)
            else:
                att.stun(self.parry_stun if mine else 1.0)
            self._mc_fx("parry", x, y)
            if mine:
                self.st["parries"] += 1
            fx.burst(x, y, ui.ACCENT, n=24, speed=360, streak=True)
            fx.ring(x, y, (150, 220, 255), radius=170, life=0.4, width=7)
            fx.star(x, y, (200, 240, 255), size=120, life=0.25)
            self._float(x, y, "PARRY!" if mine else "APARADO!", ui.ACCENT, self.big_font)
            self.camera.shake(fb.shake_power("parry"))
            fb.hitstop("parry")
            fb.flash((150, 220, 255), 0.3)
            audio.play("parry")
            audio.duck(0.5)
            if mine:
                dfn.grant_counter(1.3)
                dfn.stamina = min(dfn.max_stamina, dfn.stamina + 18)
                dfn.style += 3
                self.style_total += 3
                prof.bump("parries")
                self._float(dfn.pos.x, dfn.pos.y - dfn.height - 10, "CONTRA-ATAQUE!", (255, 215, 90))
            else:
                self.brain.on_defended("parry", self.now)
        elif res.outcome == "dodge":
            if res.perfect and mine:
                if att.damage_poise(att.max_poise * 0.35):
                    self._poise_broken(att)
                else:
                    att.stun(0.75 + (0.45 if atk.unblockable else 0.0))
                dfn.grant_counter(1.6)
                dfn.stamina = min(dfn.max_stamina, dfn.stamina + 24)
                dfn.style += 2
                self.style_total += 2
                self._mc_fx("dodge", x, y)
                self.st["perfect_dodges"] += 1
                fx.ring(x, y, (130, 200, 255), radius=200, life=0.45, width=6)
                fx.burst(x, y, (180, 225, 255), n=18, speed=380, streak=True)
                self._float(x, y, "ESQUIVA PERFEITA!", (140, 215, 255), self.big_font)
                self._float(dfn.pos.x, dfn.pos.y - dfn.height - 10, "CONTRA-ATAQUE!", (255, 215, 90))
                fb.slowmo(0.35, 0.3)
                fb.flash((140, 210, 255), 0.28)
                audio.play("whoosh")
                audio.play("coin")
                prof.bump("perfect_dodges")
            else:
                self._float(x, y, "ESQUIVA" if mine else "ESQUIVOU", ui.GREEN if mine else (200, 200, 200))
                audio.play("whoosh")
                if mine:
                    dfn.stamina = min(dfn.max_stamina, dfn.stamina + 8)
                else:
                    att.stun(0.35)
                    self.brain.on_defended("dodge", self.now)
            if mine:
                prof.bump("dodges")
                self.st["dodges"] += 1
        elif res.outcome == "block":
            self._mc_fx("block", x, y, facing)
            fx.burst(x, y, ui.BLUE, n=10, speed=300, streak=True, direction=facing)
            fx.ring(x, y, (150, 190, 255), radius=90, life=0.25, width=5)
            self._float(x, y, f"-{res.damage}", ui.BLUE)
            audio.play("block")
            fb.hitstop("hit")
            if not mine:
                att.stun(0.4)                  # o ataque "bate na parede": recuo
                self._float(att.pos.x, att.pos.y - att.height - 20, "BLOQUEADO", (190, 200, 230))
                self.brain.on_defended("block", self.now)
            else:
                dfn.style = 0
        elif res.outcome == "guardbreak":
            if mine:
                self.st["guardbreaks_taken"] += 1
                self.st["taken"] += res.damage
            fx.burst(x, y, (255, 160, 40), n=22, speed=420, streak=True)
            fx.ring(x, y, (255, 160, 40), radius=150, life=0.4, width=7)
            self._float(x, y, "GUARDA QUEBRADA!", (255, 160, 40), self.big_font)
            self.camera.shake(fb.shake_power("crit"))
            fb.hitstop("crit")
            fb.flash((255, 160, 40), 0.3)
            audio.play("crit1")
            self.hurt_flash = 1.0
            self.hud_shake = 0.5
            dfn.style = 0
        elif res.outcome in ("hit", "crit"):
            crit = res.outcome == "crit"
            if mine:
                self.st["taken"] += res.damage
                if atk.unblockable:
                    self.st["unblockable_taken"] += 1
            else:
                self.st["dealt"] += res.damage
                self.st["hits_landed"] += 1
            col = (255, 215, 90) if crit else (255, 90, 70)
            self._mc_fx("crit" if crit else "hit", x, y, facing)
            fx.burst(x, y, (255, 230, 120) if crit else (235, 70, 55), n=22 if crit else 13, speed=430, streak=True,
                     direction=facing)
            fx.burst(x, y, (255, 255, 255), n=6, speed=200, size=4)
            fx.star(x, y, (255, 245, 200) if crit else (255, 200, 170), size=140 if crit else 90, life=0.22)
            dfn.flash_color = (255, 235, 150) if crit else (190, 190, 190)
            if crit:
                fx.ring(x, y, (255, 215, 90), radius=140, life=0.35, width=6)
                fb.flash((255, 215, 90), 0.25)
            label = f"-{res.damage}"
            if res.counter:
                label += " CONTRA-ATAQUE!"
            elif crit:
                label += " CRÍTICO"
            tired = att is self.player and att.fatigue_mult() < 0.99
            self._float(x, y, label, (170, 170, 170) if (tired or res.armored) else (ui.ACCENT if crit else ui.RED),
                        self.big_font if crit else None)
            if res.armored:
                fx.burst(x, y, (190, 195, 205), n=8, speed=280, streak=True, direction=facing)
                self._float(x, y + 36, "BLINDADO", (170, 180, 195))
            if res.broke:
                self._poise_broken(dfn)
            if res.punish:
                self._float(x, y + 38, "PUNIDO!", (255, 190, 90))
            self.camera.shake(fb.shake_power("crit" if crit else "hit"))
            fb.hitstop("crit" if crit else "hit")
            audio.play("crit" if crit else "hit")
            if mine:
                dfn.style = 0
                self.hurt_flash = 1.0
                self.hud_shake = 0.4
                fb.flash((255, 60, 50), 0.18)
            else:
                prof.bump("hits_landed")
                prof.bump("damage_dealt", res.damage)
                prof.record("max_hit", res.damage)
                if crit:
                    prof.bump("crits")

    def _poise_broken(self, f) -> None:
        """A armadura do inimigo caiu: ele fica atordoado e vulnerável (dano cheio)."""
        x, y = f.pos.x, f.pos.y - f.height * 0.6
        if f is self.enemy:
            self.st["breaks"] += 1
        self._mc_fx("break", x, y)
        self.fx.burst(x, y, (255, 220, 120), n=26, speed=440, streak=True)
        self.fx.ring(x, y, (255, 220, 120), radius=210, life=0.45, width=8)
        self.fx.star(x, y, (255, 240, 190), size=150, life=0.3)
        self._float(x, y - 30, "ARMADURA QUEBRADA!", (255, 220, 120), self.big_font)
        self.fb.hitstop("crit")
        self.fb.flash((255, 220, 120), 0.3)
        self.camera.shake(self.fb.shake_power("crit"), 0.25)
        self.game.audio.play("crit1")

    def _float(self, x, y, msg, color, font=None) -> None:
        self.fx.text(x, y, (font or self.dmg_font).render(tr(msg), True, color))

    def _restart(self) -> None:
        """Recomeça esta mesma luta (mesmo desafiante/onda)."""
        self.game.scenes.replace(ArenaScene(self.game, max(self.stage, 0), challenger=self.challenger, endless=self.endless,
                                             daily=self.daily),
                                 fade="iris")

    def _fight_stats(self, won: bool) -> dict:
        p = self.player
        return {**self.st, "won": won, "time": self.now, "hp_frac": p.hp / max(1.0, p.max_hp),
                "par_time": 25.0 + self.enemy.max_hp * 0.12}

    def _finish(self) -> None:
        prof = self.game.profile
        from scenes.results import ResultsOverlay
        if self.result == "win":
            gold = self.edef.get("gold", 20)
            if self.challenger:
                first = self.challenger not in prof.collection
                prof.collection[self.challenger] = prof.collection.get(self.challenger, 0) + 1
            else:
                first = self.stage == prof.arena_stage
                cid = self.edef["character"]
                new_card = cid not in prof.collection
                prof.collection[cid] = prof.collection.get(cid, 0) + 1
            if not first and not self.endless:
                gold //= 3   # revanche rende menos
            if self.daily:
                today = roster.today_key()
                if prof.counters.get("daily_done", 0) != today:        # 1ª vez hoje: recompensa multiplicada
                    gold = int(max(gold, self.edef.get("gold", 20)) * self.daily.get("reward", 1.5))
                    prof.counters["daily_done"] = today
                    prof.bump("dailies")
            bonus = int(gold * min(0.5, 0.05 * self.style_total))       # recompensa por esquivar/aparar no tempo certo
            gold += bonus
            prof.gold += gold
            prof.wins += 1
            prof.bump("fights_won")
            if first and not self.challenger:
                prof.arena_stage += 1
            lines = [f"Você derrotou {self.enemy.name}!", f"+{gold} ouro"]
            if self.daily:
                lines.append(f"Desafio do Dia ({self.daily['name']}) concluído!" if prof.counters.get("daily_done") == roster.today_key()
                             else "Desafio do Dia")
            letter = grading.grade(self._fight_stats(True))
            lines.append(f"Nota: {letter}")
            if self.endless:
                prof.record("endless_best", self.endless)
                lines.append(f"Onda {self.endless} superada! Próxima: onda {self.endless + 1}")
            prof.history.append("W")
            prof.bump("gold_total", gold)
            prof.bump("armor_breaks", self.st["breaks"])
            prof.record("parries_fight", self.st["parries"])
            if self.player.hp >= self.player.max_hp - 0.01:
                prof.bump("flawless_wins")
            if letter == "S":
                prof.bump("rank_s")
            rar = roster.rarity(self.edef["character"])
            if (self.challenger and first) or (not self.challenger and new_card):
                lines.append(f"Carta {roster.rarity_info(rar)['label']} adicionada ao álbum!")
            for s in roster.skins():          # aparências recém-liberadas
                if roster.unlocked_skin(prof, s) and s["id"] not in prof.skins_seen:
                    prof.skins_seen.append(s["id"])
                    if s["id"] != "steve":
                        lines.append(f"Nova aparência: {s['name']}!")
            if bonus:
                lines.append(f"Bônus de estilo: +{bonus} ouro")
            if first and not self.challenger and prof.arena_stage < len(roster.enemies()):
                nxt = roster.character(roster.enemies()[prof.arena_stage]["character"])["name"]
                lines.append(f"Próximo desafiante: {nxt}")
            self.game.audio.play("coin")
            title, color = "VITÓRIA", ui.ACCENT
        else:
            lines = [f"{self.enemy.name} venceu desta vez."]
            prof.history.append("L")
            if self.endless:
                prof.record("endless_best", self.endless - 1)
            lines += grading.hints(self._fight_stats(False)) or ["Treine seus atributos e volte!"]
            title, color = "DERROTA", ui.RED
            letter = None
        for d in achievements.check(prof):
            lines.append(f"Conquista: {d['name']}")
            self.game.feedback.toast(f"Conquista: {d['name']}", (255, 205, 70), 4.0)
        self.game.save.save(prof)
        if self.endless and self.result == "win":
            nxt = roster.endless_pick(self.endless + 1, random.Random(), avoid=self.challenger)
            on_close = lambda: self.game.scenes.replace(ArenaScene(self.game, 0, challenger=nxt, endless=self.endless + 1), fade="iris")
        else:
            if self.endless:
                lines.append(f"Você chegou à onda {self.endless}. Recorde: {prof.counters.get('endless_best', 0)}")
            on_close = lambda: self.game.scenes.pop(fade=True)
        self.game.scenes.push(ResultsOverlay(self.game, title, lines,
                                             on_close=on_close, color=color,
                                             grade=letter if self.result == "win" else None))

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
        if self.intro >= INTRO_COUNT_START - 0.3:
            self._hud(surf)
        if self.in_intro:
            self._draw_intro(surf)
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
                img = self._dark(d.sprite, d.h, d.flip)
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

    def _edge_vignette(self, surf: pygame.Surface, color, alpha: float) -> None:
        """Borda colorida (vermelho = perigo/dano). Pré-renderizada por tamanho; só o alpha muda."""
        W, H = surf.get_size()
        key = (W, H, color)
        if self._vignette is None or getattr(self, "_vignette_key", None) != key:
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(46):
                pygame.draw.rect(v, (*color, int(150 * (1 - i / 46) ** 2)), (i, i, W - 2 * i, H - 2 * i), 1)
            self._vignette, self._vignette_key = v, key
        self._vignette.set_alpha(int(255 * max(0.0, min(1.0, alpha))))
        surf.blit(self._vignette, (0, 0))

    def _danger_vignette(self, surf: pygame.Surface) -> None:
        """Borda pulsando enquanto o inimigo prepara um golpe especial; vermelho = imbloqueável, laranja = quebra-guarda."""
        e = self.enemy
        if self.fb.intensity <= 0 or self.game.low_perf:
            return
        if self.hurt_flash > 0:
            self._edge_vignette(surf, (255, 30, 30), self.hurt_flash * 0.9)
            return
        if not (e.state == "windup" and e.attack is not None and (e.attack.unblockable or e.attack.guard_break)):
            return
        pulse = 0.75 if self.fb.reduce_motion else 0.55 + 0.45 * math.sin(self.now * math.tau * 1.5)
        self._edge_vignette(surf, (255, 40, 30) if e.attack.unblockable else (255, 150, 30),
                            max(0.2, pulse * min(1.0, self.fb.intensity)))

    def _status_chips(self, surf: pygame.Surface, x: int, y: int) -> None:
        """Fadiga, contra-ataque pronto e estilo do jogador, abaixo da barra de estamina."""
        p = self.player
        small = self.small
        if p.fatigue >= 2.5:
            lvl = min(4, int(p.fatigue - 1))
            ui.text(surf, small, f"FADIGA x{lvl}", (x, y), (240, 200, 90))
            y += 22
        if p.counter_ready:
            k = p.counter_time / 1.6
            col = (255, 215, 90)
            ui.text(surf, small, "CONTRA-ATAQUE PRONTO!", (x, y), col)
            pygame.draw.rect(surf, (70, 56, 20), (x, y + 21, 170, 5), border_radius=2)
            pygame.draw.rect(surf, col, (x, y + 21, int(170 * k), 5), border_radius=2)
            y += 30
        if p.style:
            ui.text(surf, small, f"ESTILO x{p.style}", (x, y), (150, 220, 255))

    def _hud(self, surf: pygame.Surface) -> None:
        W = surf.get_width()
        p, e = self.player, self.enemy
        a = self.game.assets
        self._danger_vignette(surf)
        shake = int(6 * self.hud_shake * math.sin(self.now * 60))
        # cartões de cada lutador: retrato + nome + barras
        for side, f, ghost in ((-1, p, self.ghost_p), (1, e, self.ghost_e)):
            x0 = 20 if side < 0 else W - 20
            portrait = pygame.Rect(0, 0, 78, 78)
            portrait.topleft = (x0, 14) if side < 0 else (x0 - 78, 14)
            ui.panel(surf, portrait.inflate(8, 8).move(0, 0), (16, 18, 28, 235), accent=False)
            try:
                char = roster.character(self.game.profile.character if side < 0 else self.edef["character"])
                img = a.image_h(a.thumb_path(char), 70)
                surf.blit(img, img.get_rect(midbottom=(portrait.centerx, portrait.bottom)))
            except (KeyError, StopIteration):
                pass
            bx = portrait.right + 12 if side < 0 else portrait.left - 12 - 420
            hurt = shake if f is p else 0
            ui.text(surf, self.font, f.name, (bx if side < 0 else bx + 420, 14), anchor="topleft" if side < 0 else "topright")
            if f is p:
                wi = mc.sprite(roster.weapon_icon(self.game.profile.weapon_level), 2)
                if wi is not None:
                    surf.blit(wi, (bx + self.font.size(f.name)[0] + 10, 10))
            low = f.hp / f.max_hp < 0.3 and int(self.now * 4) % 2 == 0
            frac = f.hp / f.max_hp
            mc_hud = theme.mc() and not ui.high_contrast
            if mc_hud and f is p:        # tema Minecraft: corações (pisca ao levar dano, treme com pouca vida)
                mcui.hearts(surf, bx + hurt, 42, frac, blink=ghost > frac + 0.02,
                            shake_t=self.now if frac < 0.3 else None)
            elif mc_hud:                 # inimigo: barra de chefe (segmentada na luta final)
                boss = self.stage == len(roster.enemies()) - 1
                mcui.boss_bar(surf, pygame.Rect(bx, 48, 420, 16), frac, "purple" if boss else "red",
                              notches=20 if boss else 0, rtl=True)
            else:
                ui.bar(surf, (bx + hurt, 46, 420, 24), frac, (255, 120, 90) if low else ui.RED, ghost=ghost,
                       rtl=side > 0)
            ui.text(surf, self.small, f"{int(f.hp)}/{int(f.max_hp)}", (bx + 210, 49 if not mc_hud or f is not p else 72),
                    anchor="midtop")
            if f is p:
                low_st = p.stamina < p.dodge_cost
                sta_col = (255, 150, 50) if low_st and int(self.now * 6) % 2 == 0 else ui.GREEN
                if mc_hud:
                    mcui.icons(surf, bx, 76, p.stamina / p.max_stamina, "food", k=2)
                else:
                    ui.bar(surf, (bx, 76, 300, 12), p.stamina / p.max_stamina, sta_col)
            else:
                if f.max_poise > 0 and mc_hud:
                    mcui.icons(surf, bx + 420 - 18, 68, f.poise / f.max_poise, "armor", k=2, rtl=True)
                    ui.text(surf, self.small, self.edef.get("title", ""), (bx + 420, 90), ui.ACCENT, "topright")
                    continue
                elif f.max_poise > 0:
                    broken = f.poise <= 0
                    col = (255, 120, 90) if broken else (235, 200, 90)
                    ui.bar(surf, (bx, 74, 300, 12), f.poise / f.max_poise, col, rtl=True)
                    ui.text(surf, self.small, tr("ARMADURA"), (bx + 300 - 6, 88), (215, 190, 110), "topright")
                ui.text(surf, self.small, self.edef.get("title", ""), (bx + 420, 74), ui.ACCENT, "topright")
        self._status_chips(surf, 106, 94)
        if theme.mc() and not ui.high_contrast:
            self._hotbar(surf)
        label = (f"{tr('Desafio do Dia')} · {tr(self.daily['name'])}" if self.daily else
                 f"{tr('Arena Infinita')} · {tr('Onda')} {self.endless}" if self.endless else
                 f"{tr('Desafio')} · {roster.rarity_info(roster.rarity(self.challenger))['label']}" if self.challenger
                 else f"Luta {self.stage + 1}/{len(roster.enemies())}")
        ui.text(surf, self.small, label, (W // 2, 14), (210, 210, 225), "midtop")
        if not self.game.input.touch_mode and self.intro < INTRO_TOTAL + 6:
            self._hint(surf)

    def _hotbar(self, surf: pygame.Surface) -> None:
        """Hotbar do Minecraft com os 4 recursos de combate: ataque, defesa, esquiva e contra-ataque."""
        p = self.player
        b = self.game.input.bindings

        def key(action: str) -> str:
            ks = b.get(action, [])
            k = pretty_key(ks[0]) if ks else ""
            return {"MOUSE ESQ.": "LMB", "MOUSE DIR.": "RMB", "MOUSE MEIO": "MMB"}.get(k, k[:6])
        busy = p.state
        slots = [
            {"icon": roster.weapon_icon(self.game.profile.weapon_level), "active": busy in ("windup", "active", "recover"),
             "dim": min(0.7, max(0.0, (p.fatigue - 1.5) * 0.25)), "label": key("attack")},
            {"icon": "item/iron_chestplate.png", "active": busy == "block", "label": key("block")},
            {"icon": "item/feather.png", "active": p.invulnerable, "dim": 0.65 if p.stamina < p.dodge_cost else 0.0,
             "label": key("dodge")},
            {"icon": "item/totem_of_undying.png", "active": p.counter_ready, "dim": 0.0 if p.counter_ready else 0.75},
        ]
        W, H = surf.get_size()
        mcui.hotbar(surf, (W // 2, H - 76), slots, k=3)

    def _hint(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        b = self.game.input.bindings

        def key(action: str) -> str:
            ks = b.get(action, [])
            return pretty_key(ks[0]) if ks else "-"
        move = "/".join(pretty_key(b.get(d, ["?"])[-1]) for d in ("left", "right"))
        alpha = min(1.0, max(0.0, (INTRO_TOTAL + 6 - self.intro) / 1.0))
        txt = (f"Mover: {move}   Atacar: {key('attack')}   Defender: {key('block')} (segure)   "
               f"Esquivar: {key('dodge')}   Pausa: Esc")
        img = self.small.render(tr(txt), True, (240, 240, 245))
        img.set_alpha(int(255 * alpha))
        box = img.get_rect(midbottom=(W // 2, H - 14))
        bg = pygame.Surface((box.w + 28, box.h + 10), pygame.SRCALPHA)
        pygame.draw.rect(bg, (10, 12, 22, int(170 * alpha)), bg.get_rect(), border_radius=10)
        surf.blit(bg, bg.get_rect(center=box.center))
        surf.blit(img, box)

    def debug_info(self) -> str:
        return f"Decoração desenhada {self.decor_drawn}/{len(self.decor)}"
