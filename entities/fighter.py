"""Lutador da arena (jogador ou inimigo): máquina de estados pura, sem input.

Quem controla (jogador via InputManager ou IA via entities.ai) só chama
`move/attack/set_block/dodge`. O ArenaScene lê `pending_hit` e resolve o golpe.

As artes são imagens estáticas, então TODA a animação é procedural: respiração, balanço ao andar, agachar e
esticar nos golpes (squash & stretch), recuo ao levar dano, queda ao ser derrotado, rastros, brilhos de contorno
por estado, arco de corte e escudo com energia. O `fx_queue` pede partículas (poeira, faíscas) à cena sem acoplar.

Regras de combate (pensadas para premiar leitura e reação, não spam de ataque):
  * esquiva no ÚLTIMO instante ("perfeita") abre um CONTRA-ATAQUE: golpe mais rápido, crítico garantido e +50% de dano
    contra alvo atordoado; defender no instante exato (PARRY) também;
  * atacar em sequência causa FADIGA (dano cai) e gasta estamina, que só volta depois de uma pausa;
  * golpes imbloqueáveis (!!, vermelho) pedem esquiva; golpes que quebram a guarda (laranja) pedem parry ou esquiva;
  * inimigos têm ARMADURA (postura): enquanto ela está de pé, golpes normais fazem pouco dano. Parry, esquiva perfeita
    e contra-ataque quebram a postura e deixam o inimigo atordoado e vulnerável (dano cheio e crítico).
"""
import math
import random
from dataclasses import dataclass

import pygame

from entities.entity import Entity
from systems.tween import ease_in_out_sine, ease_out_cubic


@dataclass(frozen=True)
class AttackDef:
    name: str = "golpe"
    windup: float = 0.25
    active: float = 0.10
    recover: float = 0.25
    damage_mult: float = 1.0
    stamina_cost: float = 12
    unblockable: bool = False
    guard_break: bool = False      # bloquear não adianta: quebra a guarda (parry e esquiva funcionam)
    chain: int = 0                 # quantos golpes extras vêm em seguida (combo do inimigo)
    weight: float = 1.0

    @classmethod
    def from_cfg(cls, d: dict) -> "AttackDef":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class HitResult:
    outcome: str          # "hit" | "crit" | "block" | "parry" | "dodge" | "guardbreak" | "whiff"
    damage: int = 0
    counter: bool = False    # crítico de contra-ataque
    perfect: bool = False    # esquiva no último instante
    punish: bool = False     # acertou alvo atordoado
    armored: bool = False    # o alvo estava com armadura (dano reduzido)
    broke: bool = False      # este golpe quebrou a postura do alvo


_SHADOW: pygame.Surface | None = None
_PERFECT_DODGE = 0.17        # s: o golpe cai nos primeiros instantes da esquiva = "perfeita"
_COUNTER_WINDOW = 1.6
_ATTACK_COLORS = {"normal": (255, 255, 255), "unblockable": (255, 70, 60), "guard_break": (255, 160, 40)}


def _shadow() -> pygame.Surface:
    global _SHADOW
    if _SHADOW is None:
        _SHADOW = pygame.Surface((120, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(_SHADOW, (0, 0, 0, 90), _SHADOW.get_rect())
    return _SHADOW


def attack_kind(atk: AttackDef | None) -> str:
    if atk is None:
        return "normal"
    return "unblockable" if atk.unblockable else "guard_break" if atk.guard_break else "normal"


class Fighter(Entity):
    WALK_SPEED = 260
    DODGE_TIME = 0.32
    DODGE_SPEED = 900
    HURT_TIME = 0.22
    COMBO_WINDOW = 0.35
    REGEN_DELAY = 0.9            # s sem recuperar estamina depois de gastá-la (golpe, esquiva)
    BLOCK_DRAIN = 5.0            # estamina/s gasta segurando a guarda

    def __init__(self, name: str, sprite: str, x: float, y: float, *, hp: float, damage: float,
                 stamina: float, stamina_regen: float, block_reduction: float, parry_window: float,
                 crit_chance: float, crit_mult: float, dodge_cost: float, attacks: list[AttackDef],
                 facing: int = 1, height: int = 230, reach: float = 190, sprite_faces: int = 1,
                 stagger_resist: float = 0.0) -> None:
        super().__init__(x, y, 120, height)
        self.name, self.sprite = name, sprite
        self.max_hp = self.hp = hp
        self.damage = damage
        self.max_stamina = self.stamina = stamina
        self.stamina_regen = stamina_regen
        self.block_reduction = block_reduction
        self.parry_window = parry_window
        self.crit_chance, self.crit_mult = crit_chance, crit_mult
        self.dodge_cost = dodge_cost
        self.attacks = attacks
        self.facing = facing
        self.sprite_faces = sprite_faces     # para qual lado a arte original olha (1 = direita)
        self.height = height
        self.reach = reach
        self.stagger_resist = stagger_resist   # chance de NÃO ser interrompido ao levar dano atacando
        self.state = "idle"
        self.timer = 0.0
        self.attack: AttackDef | None = None
        self.combo = 0
        self._combo_timer = 0.0
        self._queued_attack = False
        self.block_started = -99.0
        self.pending_hit: AttackDef | None = None
        self._move = 0
        self.flash = 0.0
        self.flash_color = (150, 150, 150)
        self.anim_t = random.random() * 10
        # --- combate ---
        self.fatigue = 0.0              # sobe a cada golpe; reduz o dano e some com a pausa
        self._idle_time = 0.0
        self.counter_time = 0.0         # janela de contra-ataque (depois de esquiva perfeita / parry)
        self.regen_delay = 0.0
        self.style = 0                  # pontos de "estilo" (esquivas perfeitas e parries) da luta
        # --- postura / armadura (só inimigos; max_poise 0 = sem armadura) ---
        self.max_poise = 0.0
        self.poise = 0.0
        self.armor = 0.45               # fração do dano que passa enquanto a armadura está de pé
        self._broken = False
        self._since_hit = 0.0
        # --- animação / efeitos ---
        self.ghosts_on = True               # desligado no modo de baixo desempenho
        self.ghosts: list[list] = []        # rastro: [x, y, vida, superfície]
        self._ghost_cd = 0.0
        self.fx_queue: list[tuple] = []     # pedidos de partículas para a cena: ("dust", x, y) etc.
        self._dust_cd = 0.0
        self.squash = 0.0                   # impulso de achatamento (1 -> 0) ao levar/aplicar golpe
        self.kb = 0.0                       # recuo visual ao levar dano (1 -> 0)
        self.slash_t = 0.0                  # arco do corte (visível um instante depois do golpe)
        self.slash_kind = "normal"
        self.slash_counter = False          # o corte atual é um contra-ataque (dourado)
        self.block_flash = 0.0              # ondulação no escudo quando bloqueia
        self.spawn_t = 0.0                  # >0: aterrissagem da entrada (achatar e quicar)
        self.fade = 1.0
        self._tint_cache: dict = {}

    # --- propriedades de regra -----------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self.state in ("windup", "strike", "recover", "dodge", "hurt", "stunned", "dead")

    @property
    def invulnerable(self) -> bool:
        return self.state == "dodge" and self.timer < self.DODGE_TIME * 0.85

    @property
    def counter_ready(self) -> bool:
        return self.counter_time > 0 and self.state != "dead"

    @property
    def in_parry_window(self) -> bool:
        return self.state == "block" and self.timer <= self.parry_window

    def fatigue_mult(self) -> float:
        """Dano cai 12% por golpe além do 2º em sequência (mínimo 50%)."""
        return max(0.5, 1.0 - 0.12 * max(0.0, self.fatigue - 2.0))

    def _windup_time(self) -> float:
        return self.attack.windup * (0.62 if self.counter_time > 0 else 1.0)   # contra-ataque é mais rápido

    # --- comandos ---------------------------------------------------------------------------
    def move(self, direction: int) -> None:
        self._move = direction

    def _spend(self, amount: float) -> None:
        self.stamina = max(0.0, self.stamina - amount)
        self.regen_delay = self.REGEN_DELAY

    def attack_cmd(self, attack: AttackDef | None = None) -> bool:
        if self.state == "recover" and self._combo_timer > 0:
            self._queued_attack = True   # encadeia combo
            return True
        if self.busy or self.state == "block":
            return False
        atk = attack or self.attacks[min(self.combo, len(self.attacks) - 1)]
        if self.stamina < atk.stamina_cost:
            return False
        self._spend(atk.stamina_cost)
        self.fatigue += 1.0
        self._idle_time = 0.0
        self.attack = atk
        self._set("windup")
        return True

    def set_block(self, on: bool, now: float) -> None:
        if on and self.state in ("idle", "walk") and self.stamina > 3:
            self._set("block")
            self.block_started = now
        elif not on and self.state == "block":
            self._set("idle")

    def dodge(self) -> bool:
        if self.busy or self.stamina < self.dodge_cost:
            return False
        self._spend(self.dodge_cost)
        self._set("dodge")
        self.fx_queue.append(("dust", self.pos.x, self.pos.y, 6))
        return True

    def stun(self, seconds: float) -> None:
        if self.state != "dead":
            self._set("stunned")
            self.timer = -seconds  # conta até 0
            self.attack = None
            self.combo = 0
            self.counter_time = 0.0
            self._queued_attack = False

    def grant_counter(self, seconds: float = _COUNTER_WINDOW) -> None:
        self.counter_time = max(self.counter_time, seconds)

    def damage_poise(self, amount: float) -> bool:
        """Reduz a postura; True se este golpe QUEBROU a armadura (alvo fica atordoado e vulnerável)."""
        if self.max_poise <= 0 or self._broken or self.state == "dead":
            return False
        self.poise -= amount
        self._since_hit = 0.0
        if self.poise <= 0:
            self.poise = 0.0
            self._broken = True
            self.stun(1.3)
            return True
        return False

    # --- simulação --------------------------------------------------------------------------
    def _set(self, state: str) -> None:
        self.state, self.timer = state, 0.0

    def update(self, dt: float, bounds: tuple[float, float]) -> None:
        self.anim_t += dt
        self.timer += dt
        self.flash = max(0.0, self.flash - dt)
        self.squash = max(0.0, self.squash - dt * 5.0)
        self.kb = max(0.0, self.kb - dt * 4.5)
        self.slash_t = max(0.0, self.slash_t - dt)
        self.block_flash = max(0.0, self.block_flash - dt * 4.0)
        self.spawn_t = max(0.0, self.spawn_t - dt)
        self.counter_time = max(0.0, self.counter_time - dt)
        self.regen_delay = max(0.0, self.regen_delay - dt)
        self._ghost_cd = max(0.0, self._ghost_cd - dt)
        self._dust_cd = max(0.0, self._dust_cd - dt)
        if self.ghosts:
            for g in self.ghosts:
                g[2] -= dt
            self.ghosts = [g for g in self.ghosts if g[2] > 0]
        self._combo_timer = max(0.0, self._combo_timer - dt)
        self._since_hit += dt
        if self.max_poise > 0 and not self._broken and self._since_hit > 2.5:       # armadura se recompõe
            self.poise = min(self.max_poise, self.poise + self.max_poise * 0.10 * dt)

        # estamina: pausa depois de gastar; guarda levantada consome
        if self.state == "block":
            self.stamina = max(0.0, self.stamina - self.BLOCK_DRAIN * dt)
        elif self.regen_delay <= 0:
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen * dt)
        # fadiga some quando a pessoa para de atacar
        if self.state in ("idle", "walk", "block"):
            self._idle_time += dt
            if self._idle_time > 0.7:
                self.fatigue = max(0.0, self.fatigue - 1.1 * dt)

        s = self.state
        if s in ("idle", "walk"):
            self.state = "walk" if self._move else "idle"
            self.pos.x += self._move * self.WALK_SPEED * dt
            if self._move and self._dust_cd <= 0:
                self._dust_cd = 0.17
                self.fx_queue.append(("dust", self.pos.x - self._move * 20, self.pos.y, 1))
            if self._combo_timer <= 0:
                self.combo = 0
        elif s == "block" and self.stamina <= 0:
            self._set("idle")                       # guarda caiu por falta de estamina
        elif s == "windup" and self.timer >= self._windup_time():
            self._set("strike")
            self.pending_hit = self.attack
            self.pos.x += self.facing * 24
            self.slash_t, self.slash_kind = 0.22, attack_kind(self.attack)
            self.slash_counter = self.counter_time > 0
            self.squash = 0.5
            self.fx_queue.append(("lunge", self.pos.x, self.pos.y, self.facing))
        elif s == "strike" and self.timer >= self.attack.active:
            self._set("recover")
            self._combo_timer = self.COMBO_WINDOW + self.attack.recover
        elif s == "recover" and self.timer >= self.attack.recover:
            self.combo = (self.combo + 1) % max(1, len(self.attacks))
            self._set("idle")
            if self._queued_attack:
                self._queued_attack = False
                self.attack_cmd()
        elif s == "dodge":
            k = max(0.0, 1 - self.timer / self.DODGE_TIME)
            self.pos.x -= self.facing * self.DODGE_SPEED * k * dt
            if self.timer >= self.DODGE_TIME:
                self._set("idle")
        elif s == "hurt" and self.timer >= self.HURT_TIME:
            self._set("idle")
        elif s == "stunned" and self.timer >= 0:
            self._set("idle")
            if self._broken:                      # saiu do atordoamento da quebra: armadura volta cheia
                self._broken = False
                self.poise = self.max_poise
        self._move = 0
        self.pos.x = max(bounds[0], min(bounds[1], self.pos.x))

    def receive(self, atk: AttackDef, attacker: "Fighter", now: float) -> HitResult:
        """Resolve um golpe recebido: esquiva > parry > bloqueio > dano."""
        if self.state == "dead":
            return HitResult("whiff")
        if self.invulnerable:
            return HitResult("dodge", perfect=self.timer <= _PERFECT_DODGE)
        base = attacker.damage * atk.damage_mult * attacker.fatigue_mult()
        if self.state == "block" and not atk.unblockable:
            if now - self.block_started <= self.parry_window:
                self.block_flash = 1.0
                return HitResult("parry")
            self.block_flash = 1.0
            self.squash = max(self.squash, 0.4)
            if atk.guard_break:                       # a guarda quebra: dano quase cheio e atordoa
                dmg = max(1, round(base * (1 - self.block_reduction * 0.35)))
                self._spend(self.stamina)
                self._apply(dmg, hurt=False)
                self.stun(0.9)
                return HitResult("guardbreak", dmg)
            dmg = max(1, round(base * (1 - self.block_reduction)))
            self._spend(atk.stamina_cost * 1.5)
            self._apply(dmg, hurt=False)
            if self.stamina <= 0:          # guarda quebrada
                self.stun(0.8)
            return HitResult("block", dmg)
        counter = attacker.counter_time > 0
        punish = self.state == "stunned"
        crit = counter or random.random() < attacker.crit_chance
        mult = attacker.crit_mult if crit else 1.0
        if counter:
            mult *= 1.5
            attacker.counter_time = 0.0
        if punish:
            mult *= 1.5
        dmg = max(1, round(base * mult * random.uniform(0.9, 1.1)))
        armored = self.max_poise > 0 and self.poise > 0 and not punish and not counter
        broke = False
        if armored:                                 # armadura de pé: pouco dano, e a postura vai cedendo
            raw = dmg
            dmg = max(1, round(dmg * self.armor))
            self._apply(dmg, hurt=True, force_stagger=False)
            broke = self.damage_poise(raw * 0.35)
        else:
            self._apply(dmg, hurt=True, force_stagger=counter)
            if counter:
                broke = self.damage_poise(self.max_poise * 0.5)
        return HitResult("crit" if crit else "hit", dmg, counter=counter, punish=punish, armored=armored and not broke,
                         broke=broke)

    def _apply(self, dmg: int, hurt: bool, force_stagger: bool = False) -> None:
        self.hp = max(0, self.hp - dmg)
        self.flash = 0.12
        self.squash = 1.0 if hurt else max(self.squash, 0.5)
        if self.hp <= 0:
            self._set("dead")
        elif hurt and not force_stagger and self.state in ("windup", "strike") and random.random() < self.stagger_resist:
            pass   # "super armor": aguenta o golpe e continua o ataque
        elif hurt and self.state not in ("stunned",):
            self.attack = None
            self._queued_attack = False
            self._set("hurt")
            self.pos.x -= self.facing * 30
            self.kb = 1.0

    # --- render -----------------------------------------------------------------------------
    def _pose(self) -> tuple[float, float, float, float, float, int]:
        """(escala x, escala y, ângulo, deslocamento x, deslocamento y, alpha) conforme o estado."""
        s, t = self.state, self.timer
        sx = sy = 1.0
        ang = dx = dy = 0.0
        alpha = 255
        br = math.sin(self.anim_t * 3.1)
        if s in ("idle", "block"):
            sy, sx = 1 + 0.02 * br, 1 - 0.01 * br
            if s == "block":
                sy, dx = sy * 0.97, -6
        elif s == "walk":
            ph = self.anim_t * 10
            dy, ang = -abs(math.sin(ph)) * 8, 3 * math.sin(ph)
            sx, sy = 1 + 0.02 * math.sin(ph * 2), 1 - 0.02 * math.sin(ph * 2)
        elif s == "windup" and self.attack:
            k = ease_out_cubic(min(1.0, t / max(self._windup_time(), 0.01)))
            sy, sx, ang, dx = 1 - 0.10 * k, 1 + 0.07 * k, 11 * k, -20 * k
        elif s == "strike":
            sx, sy, ang, dx = 1.16, 0.92, -16, 36
        elif s == "recover" and self.attack:
            r = ease_in_out_sine(min(1.0, t / max(self.attack.recover, 0.01)))
            sx, sy, ang, dx = 1.16 - 0.16 * r, 0.92 + 0.08 * r, -16 * (1 - r), 36 * (1 - r)
        elif s == "hurt":
            u = min(1.0, t / self.HURT_TIME)
            ang, dx = 12 * (1 - u), -34 * (1 - u) ** 2
        elif s == "stunned":
            ang = 7 * math.sin(self.anim_t * 14)
            sy = 0.97
        elif s == "dodge":
            k = min(1.0, t / self.DODGE_TIME)
            ang, sy, sx, alpha = 18 * (1 - 0.5 * k), 0.9, 1.12, 150
        elif s == "dead":
            u = min(1.0, t * 2.2)
            ang, dy = 82 * ease_out_cubic(u), 14 * u
            alpha = int(255 * (1 - min(1.0, max(0.0, (t - 0.9) / 1.4))) * self.fade)
        if self.spawn_t > 0:       # aterrissagem da entrada: quica e achata
            u = self.spawn_t / 0.45
            sy, sx = sy * (1 - 0.2 * u), sx * (1 + 0.16 * u)
        if self.squash > 0 and s not in ("dead", "windup", "strike"):    # achatamento rápido ao levar golpe
            sx, sy = sx + 0.12 * self.squash, sy - 0.12 * self.squash
        return sx, sy, ang, dx, dy, alpha

    def _tint(self, img: pygame.Surface, color) -> pygame.Surface:
        t = img.copy()
        t.fill(color, special_flags=pygame.BLEND_RGB_MULT)
        return t

    def _outline_color(self) -> tuple | None:
        """Cor do contorno brilhante do estado atual (ou None)."""
        if self.state == "windup" and self.attack:
            k = min(1.0, self.timer / max(self._windup_time(), 0.01))
            c = _ATTACK_COLORS[attack_kind(self.attack)]
            return tuple(int(v * (0.35 + 0.65 * k)) for v in c)
        if self.counter_ready:
            pulse = 0.65 + 0.35 * math.sin(self.anim_t * 14)
            return (int(255 * pulse), int(205 * pulse), int(70 * pulse))
        if self.in_parry_window:
            return (140, 230, 255)
        return None

    def draw(self, surf: pygame.Surface, camera, assets, font) -> None:
        sx_, sy_ = camera.to_screen(self.pos.x, self.pos.y)
        flip = self.facing != self.sprite_faces
        base = assets.image_h(self.sprite, self.height, flip)
        scx, scy, angle, dx, dy, alpha = self._pose()
        s, t = self.state, self.timer
        img = base
        if (scx, scy) != (1.0, 1.0):
            w, h = base.get_size()
            img = pygame.transform.smoothscale(base, (max(4, int(w * scx)), max(4, int(h * scy))))
        if angle:
            img = pygame.transform.rotate(img, angle * self.facing)
        if self.flash > 0:
            img = img.copy()
            c = self.flash_color
            img.fill((int(c[0] * self.flash / 0.12), int(c[1] * self.flash / 0.12), int(c[2] * self.flash / 0.12)),
                     special_flags=pygame.BLEND_RGB_ADD)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)

        # rastro (esquiva e golpe): "fantasmas" que somem
        if self.ghosts_on and self._ghost_cd <= 0 and len(self.ghosts) < 5 and s in ("dodge", "strike"):
            self._ghost_cd = 0.045 if s == "dodge" else 0.03
            tint = (150, 200, 255) if s == "dodge" else _ATTACK_COLORS[attack_kind(self.attack)]
            ghost = self._tint(img, tint)
            self.ghosts.append([self.pos.x + dx * self.facing, self.pos.y, 0.22, ghost])
        for gx, gy, life, gimg in self.ghosts:
            gsx, gsy = camera.to_screen(gx, gy)
            gimg.set_alpha(int(125 * life / 0.22))
            surf.blit(gimg, gimg.get_rect(midbottom=(gsx, gsy + 4)))

        # sombra (encolhe quando o personagem "salta")
        shadow = _shadow()
        k_sh = 1.0 - min(0.4, max(0.0, -dy) / 40)
        if k_sh < 0.99:
            shadow = pygame.transform.smoothscale(shadow, (int(120 * k_sh), int(24 * k_sh)))
        surf.blit(shadow, shadow.get_rect(center=(sx_, sy_ - 2)))

        rect = img.get_rect(midbottom=(sx_ + dx * self.facing, sy_ + 4 + dy))
        if rect.width > 180:   # criaturas largas: frente do corpo fica na posição lógica, cauda para trás
            rect.centerx -= int(self.facing * (rect.width / 2 - 90))
        oc = self._outline_color()
        if oc:     # contorno brilhante: 4 cópias tingidas deslocadas por baixo da arte
            tinted = self._tint(img, oc)
            for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
                surf.blit(tinted, rect.move(ox, oy), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(img, rect)

        front = sx_ + self.facing * 70
        if s == "block":
            self._draw_shield(surf, front, sy_)
        if self.slash_t > 0:
            self._draw_slash(surf, sx_, sy_)
        if s == "windup" and self.attack:
            self._draw_telegraph(surf, sx_, sy_, font)
        elif s == "stunned":
            for i in range(3):
                a = self.anim_t * 5 + i * 2.1
                pygame.draw.circle(surf, (255, 230, 90),
                                   (int(sx_ + math.cos(a) * 34), int(sy_ - self.height - 12 + math.sin(a) * 8)), 6)
        if self.counter_ready:
            self._draw_counter_marker(surf, sx_, sy_, font)

    # --- efeitos desenhados ------------------------------------------------------------------
    def _draw_shield(self, surf, front, sy) -> None:
        """Escudo de energia: setor translúcido na frente do lutador; branco-azulado no instante de parry e
        com ondulação ao bloquear."""
        ready = self.in_parry_window
        glow = max(self.block_flash, 1.0 if ready else 0.0)
        col = tuple(int(v + (255 - v) * glow) for v in (120, 170, 255))
        r = 84 + int(12 * self.block_flash)
        dome = pygame.Surface((r + 6, r * 2 + 6), pygame.SRCALPHA)
        cy = r + 3
        pts = [(2, cy)] + [(2 + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r)
                           for a in range(-64, 65, 8)]
        pygame.draw.polygon(dome, (*col, int(44 + 70 * glow)), pts)
        pygame.draw.lines(dome, (*col, int(170 + 85 * glow)), False, pts[1:], 5 if ready else 3)
        for i in range(3):          # reflexos que passeiam pelo escudo
            a = math.radians(-50 + ((self.anim_t * 70 + i * 40) % 100))
            pygame.draw.circle(dome, (255, 255, 255, 120), (2 + int(math.cos(a) * r), cy + int(math.sin(a) * r)), 4)
        if self.facing < 0:
            dome = pygame.transform.flip(dome, True, False)
        x0 = front - self.facing * 60
        pos_x = x0 if self.facing > 0 else x0 - dome.get_width()
        surf.blit(dome, (pos_x, sy - self.height * 0.5 - cy))
        if ready:
            pygame.draw.circle(surf, (210, 245, 255), (int(front + self.facing * 14), int(sy - self.height * 0.5)), 10, 3)

    def _draw_slash(self, surf, sx, sy) -> None:
        """Arco do corte: meia-lua que "varre" e some, na cor do tipo de golpe."""
        p = 1 - self.slash_t / 0.22
        col = (255, 215, 90) if self.slash_counter else _ATTACK_COLORS[self.slash_kind]
        cx = sx + self.facing * self.reach * 0.28
        cy = sy - self.height * 0.52
        R = self.reach * 0.92
        a_end = -75 + 135 * min(1.0, p * 1.7)        # graus; o arco avança rápido
        a_start = max(-75, a_end - 80)
        n = 9
        for i in range(n):
            a0 = a_start + (a_end - a_start) * i / n
            a1 = a_start + (a_end - a_start) * (i + 1) / n
            thick = 6 + 46 * (i + 1) / n
            alpha = int(215 * ((i + 1) / n) ** 1.6 * (1 - p * 0.75))

            def pt(a, rad):
                ar = math.radians(a)
                return (cx + self.facing * math.cos(ar) * rad, cy + math.sin(ar) * rad)
            poly = [pt(a0, R), pt(a1, R), pt(a1, R - thick), pt(a0, R - thick)]
            xs, ys = [q[0] for q in poly], [q[1] for q in poly]
            box = pygame.Rect(min(xs) - 2, min(ys) - 2, max(xs) - min(xs) + 4, max(ys) - min(ys) + 4)
            seg = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.polygon(seg, (*col, alpha), [(x - box.x, y - box.y) for x, y in poly])
            surf.blit(seg, box)

    def _draw_telegraph(self, surf, sx, sy, font) -> None:
        kind = attack_kind(self.attack)
        k = min(1.0, self.timer / max(self._windup_time(), 0.01))
        col = _ATTACK_COLORS[kind]
        cx, cy = int(sx), int(sy - self.height - 30)
        pulse = 1.0 + (0.12 * math.sin(self.anim_t * 22) if kind != "normal" else 0.0)
        pygame.draw.circle(surf, col, (cx, cy), int((10 + 14 * k) * pulse), 3)
        mark = font.render("!!" if kind == "unblockable" else "!", True, col)
        surf.blit(mark, mark.get_rect(center=(cx, cy)))
        if kind == "guard_break":       # escudo quebrado ao lado da exclamação
            pygame.draw.polygon(surf, col, [(cx + 22, cy - 8), (cx + 38, cy - 8), (cx + 38, cy + 4), (cx + 30, cy + 14),
                                            (cx + 22, cy + 4)], 2)
            pygame.draw.line(surf, col, (cx + 24, cy - 10), (cx + 36, cy + 12), 2)
        if kind != "normal":            # anel de perigo que se fecha no alvo
            rr = int(60 - 40 * k)
            pygame.draw.circle(surf, col, (cx, cy), rr, 2)

    def _draw_counter_marker(self, surf, sx, sy, font) -> None:
        """Ícone dourado + barra: avisa que o PRÓXIMO golpe é um contra-ataque."""
        k = self.counter_time / _COUNTER_WINDOW
        cx, cy = int(sx), int(sy - self.height - 62)
        pulse = 1 + 0.1 * math.sin(self.anim_t * 16)
        pygame.draw.circle(surf, (255, 215, 90), (cx, cy), int(16 * pulse), 3)
        pygame.draw.line(surf, (255, 215, 90), (cx - 7, cy + 7), (cx + 7, cy - 7), 3)
        pygame.draw.line(surf, (255, 215, 90), (cx - 7, cy - 1), (cx - 1, cy - 7), 3)
        pygame.draw.rect(surf, (60, 50, 20), (cx - 22, cy + 22, 44, 6), border_radius=3)
        pygame.draw.rect(surf, (255, 215, 90), (cx - 22, cy + 22, int(44 * k), 6), border_radius=3)
