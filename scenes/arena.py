"""Arena de combate em tempo real.

Controles: mover (esq/dir), atacar (J/Z), bloquear segurando (K/X),
esquivar (L/C/Shift). Bloquear no instante do golpe = PARRY (atordoa).
Avisos vermelhos (!!) são imbloqueáveis: esquive!

O cenário é largo e cheio de decoração/plateia; tudo passa pelo SpatialGrid
e só o que a câmera enxerga é desenhado (veja F3 -> "decoração desenhada").
"""
import random

import pygame

from core import config, ui
from core.input import VirtualButton
from core.scene import Scene
from entities import roster
from entities.ai import EnemyBrain
from systems import backdrop
from systems.culling import Camera, SpatialGrid
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
        self.brain = EnemyBrain(self.enemy, self.player, self.edef.get("ai", {}))
        W, H = game.display.width, game.display.height
        self.camera = Camera(W, H, pygame.Rect(0, -200, WORLD_W, H + 200))
        self.camera.view.center = (mid, GROUND_Y - 260)
        self.fx = ParticleSystem(500)
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

    # --- ciclo de vida ------------------------------------------------------------------
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
            self.game.scenes.pop(fade=True)
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
        self.fx.update(dt)
        self.camera.follow((p.pos.x + e.pos.x) / 2, GROUND_Y - 260, dt)
        self.camera.update(dt)

        if self.result is None and (p.state == "dead" or e.state == "dead"):
            self.result = "win" if e.state == "dead" else "lose"
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

    def _resolve(self, att, dfn) -> None:
        atk, att.pending_hit = att.pending_hit, None
        if abs(dfn.pos.x - att.pos.x) > att.reach + 20:
            return
        res = dfn.receive(atk, att, self.now)
        x, y = dfn.pos.x, dfn.pos.y - dfn.height * 0.6
        audio = self.game.audio
        if res.outcome == "parry":
            att.stun(self.parry_stun)
            self.fx.burst(x, y, ui.ACCENT, n=24, speed=360)
            self._float(x, y, "PARRY!", ui.ACCENT)
            self.camera.shake(6)
            audio.play("parry")
        elif res.outcome == "dodge":
            self._float(x, y, "ESQUIVA", ui.GREEN)
            audio.play("miss")
        elif res.outcome == "block":
            self.fx.burst(x, y, ui.BLUE, n=8)
            self._float(x, y, f"-{res.damage}", ui.BLUE)
            audio.play("block")
        elif res.outcome in ("hit", "crit"):
            crit = res.outcome == "crit"
            self.fx.burst(x, y, (255, 230, 120) if crit else (230, 60, 50), n=20 if crit else 12)
            self._float(x, y, f"-{res.damage}" + (" CRÍTICO" if crit else ""), ui.ACCENT if crit else ui.RED)
            self.camera.shake(10 if crit else 5)
            audio.play("crit" if crit else "hit")

    def _float(self, x, y, msg, color) -> None:
        self.fx.text(x, y, self.dmg_font.render(msg, True, color))

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
    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        cam = self.camera
        # fundo com parallax barato: 1 blit de superfície cacheada
        bg = backdrop.build("arena", (W + 400, H), GROUND_Y - 40, self.game.assets)
        surf.blit(bg, (-max(0.0, min(400.0, cam.view.x * 0.2)), 0))
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
        self._hud(surf)
        self.game.input.draw_virtual_buttons(surf, self.font)

    def _hud(self, surf: pygame.Surface) -> None:
        W = surf.get_width()
        p, e = self.player, self.enemy
        ui.text(surf, self.font, p.name, (24, 16))
        ui.bar(surf, (24, 48, 420, 22), p.hp / p.max_hp, ui.RED)
        ui.text(surf, self.small, f"{int(p.hp)}/{int(p.max_hp)}", (234, 50), anchor="midtop")
        ui.bar(surf, (24, 76, 300, 12), p.stamina / p.max_stamina, ui.GREEN)
        ui.text(surf, self.font, e.name, (W - 24, 16), anchor="topright")
        ui.bar(surf, (W - 444, 48, 420, 22), e.hp / e.max_hp, ui.RED)
        ui.text(surf, self.small, self.edef.get("title", ""), (W - 24, 76), ui.ACCENT, "topright")
        if not self.game.input.touch_mode and self.now < 6:
            ui.text(surf, self.small, "Mover: setas/AD   Atacar: J   Defender: K (segure)   Esquivar: L / Shift",
                    (W // 2, 110), anchor="midtop")

    def debug_info(self) -> str:
        return f"Decoração desenhada {self.decor_drawn}/{len(self.decor)}"
