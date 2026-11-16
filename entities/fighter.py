"""Lutador da arena (jogador ou inimigo): máquina de estados pura, sem input.

Quem controla (jogador via InputManager ou IA via entities.ai) só chama
`move/attack/set_block/dodge`. O ArenaScene lê `pending_hit` e resolve o golpe.
A animação é procedural (inclinação, avanço, squash) para funcionar com
qualquer imagem estática — ideal para os renders dos personagens UCDM.
"""
import math
import random
from dataclasses import dataclass

import pygame

from entities.entity import Entity


@dataclass(frozen=True)
class AttackDef:
    name: str = "golpe"
    windup: float = 0.25
    active: float = 0.10
    recover: float = 0.25
    damage_mult: float = 1.0
    stamina_cost: float = 12
    unblockable: bool = False
    weight: float = 1.0

    @classmethod
    def from_cfg(cls, d: dict) -> "AttackDef":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class HitResult:
    outcome: str          # "hit" | "crit" | "block" | "parry" | "dodge" | "whiff"
    damage: int = 0


_SHADOW: pygame.Surface | None = None


def _shadow() -> pygame.Surface:
    global _SHADOW
    if _SHADOW is None:
        _SHADOW = pygame.Surface((120, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(_SHADOW, (0, 0, 0, 90), _SHADOW.get_rect())
    return _SHADOW


class Fighter(Entity):
    WALK_SPEED = 260
    DODGE_TIME = 0.32
    DODGE_SPEED = 900
    HURT_TIME = 0.22
    COMBO_WINDOW = 0.35

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
        self.anim_t = random.random() * 10
        self._flash_cache: dict = {}
        self.ghosts_on = True               # desligado no modo de baixo desempenho
        self.ghosts: list[list] = []         # rastro de esquiva: [x, y, vida, superfície]
        self._ghost_cd = 0.0

    # --- comandos ---------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self.state in ("windup", "strike", "recover", "dodge", "hurt", "stunned", "dead")

    @property
    def invulnerable(self) -> bool:
        return self.state == "dodge" and self.timer < self.DODGE_TIME * 0.85

    def move(self, direction: int) -> None:
        self._move = direction

    def attack_cmd(self, attack: AttackDef | None = None) -> bool:
        if self.state == "recover" and self._combo_timer > 0:
            self._queued_attack = True   # encadeia combo
            return True
        if self.busy or self.state == "block":
            return False
        atk = attack or self.attacks[min(self.combo, len(self.attacks) - 1)]
        if self.stamina < atk.stamina_cost:
            return False
        self.stamina -= atk.stamina_cost
        self.attack = atk
        self._set("windup")
        return True

    def set_block(self, on: bool, now: float) -> None:
        if on and self.state in ("idle", "walk"):
            self._set("block")
            self.block_started = now
        elif not on and self.state == "block":
            self._set("idle")

    def dodge(self) -> bool:
        if self.busy or self.stamina < self.dodge_cost:
            return False
        self.stamina -= self.dodge_cost
        self._set("dodge")
        return True

    def stun(self, seconds: float) -> None:
        if self.state != "dead":
            self._set("stunned")
            self.timer = -seconds  # conta até 0
            self.attack = None
            self.combo = 0

    # --- simulação --------------------------------------------------------------------
    def _set(self, state: str) -> None:
        self.state, self.timer = state, 0.0

    def update(self, dt: float, bounds: tuple[float, float]) -> None:
        self.anim_t += dt
        self.timer += dt
        self.flash = max(0.0, self.flash - dt)
        self._ghost_cd = max(0.0, self._ghost_cd - dt)
        if self.ghosts:
            for g in self.ghosts:
                g[2] -= dt
            self.ghosts = [g for g in self.ghosts if g[2] > 0]
        self._combo_timer = max(0.0, self._combo_timer - dt)
        regen = self.stamina_regen * (0.35 if self.state == "block" else 1.0)
        self.stamina = min(self.max_stamina, self.stamina + regen * dt)

        s = self.state
        if s in ("idle", "walk"):
            self.state = "walk" if self._move else "idle"
            self.pos.x += self._move * self.WALK_SPEED * dt
            if self._combo_timer <= 0:
                self.combo = 0
        elif s == "windup" and self.timer >= self.attack.windup:
            self._set("strike")
            self.pending_hit = self.attack
            self.pos.x += self.facing * 24
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
        self._move = 0
        self.pos.x = max(bounds[0], min(bounds[1], self.pos.x))

    def receive(self, atk: AttackDef, attacker: "Fighter", now: float) -> HitResult:
        """Resolve um golpe recebido aplicando esquiva > parry > bloqueio > dano."""
        if self.state == "dead":
            return HitResult("whiff")
        if self.invulnerable:
            return HitResult("dodge")
        base = attacker.damage * atk.damage_mult
        if self.state == "block" and not atk.unblockable:
            if now - self.block_started <= self.parry_window:
                return HitResult("parry")
            dmg = max(1, round(base * (1 - self.block_reduction)))
            self.stamina = max(0.0, self.stamina - atk.stamina_cost * 1.5)
            self._apply(dmg, hurt=False)
            if self.stamina <= 0:          # guarda quebrada
                self.stun(0.8)
            return HitResult("block", dmg)
        crit = random.random() < attacker.crit_chance
        dmg = max(1, round(base * (attacker.crit_mult if crit else 1.0) * random.uniform(0.9, 1.1)))
        self._apply(dmg, hurt=True)
        return HitResult("crit" if crit else "hit", dmg)

    def _apply(self, dmg: int, hurt: bool) -> None:
        self.hp = max(0, self.hp - dmg)
        self.flash = 0.12
        if self.hp <= 0:
            self._set("dead")
        elif hurt and self.state in ("windup", "strike") and random.random() < self.stagger_resist:
            pass   # "super armor": aguenta o golpe e continua o ataque
        elif hurt and self.state not in ("stunned",):
            self.attack = None
            self._queued_attack = False
            self._set("hurt")
            self.pos.x -= self.facing * 30

    # --- render -----------------------------------------------------------------------
    def draw(self, surf: pygame.Surface, camera, assets, font) -> None:
        sx, sy = camera.to_screen(self.pos.x, self.pos.y)
        flip = self.facing != self.sprite_faces
        img = assets.image_h(self.sprite, self.height, flip)
        angle, dx, squash = 0.0, 0.0, 1.0
        s, t = self.state, self.timer
        if s in ("idle", "block"):
            squash = 1 + 0.015 * math.sin(self.anim_t * 4)
        elif s == "walk":
            squash = 1 + 0.03 * abs(math.sin(self.anim_t * 10))
        elif s == "windup":
            k = min(1.0, t / self.attack.windup)
            angle, dx = 10 * k, -16 * k
        elif s == "strike":
            angle, dx = -14, 30
        elif s == "recover":
            angle = -6 * (1 - t / max(self.attack.recover, 0.01))
        elif s in ("hurt", "stunned"):
            angle = 8 + (3 * math.sin(self.anim_t * 30) if s == "stunned" else 0)
        elif s == "dodge":
            angle, squash = 18, 0.92
        elif s == "dead":
            angle = 80 * min(1.0, t * 3)
        if squash != 1.0:
            w, h = img.get_size()
            img = pygame.transform.scale(img, (int(w / squash), int(h * squash)))
        if angle:
            img = pygame.transform.rotate(img, angle * self.facing)
        if self.flash > 0:
            img = img.copy()
            img.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
        if s == "dodge":
            img = img.copy()
            img.set_alpha(140)

        # rastro de esquiva (até 5 "fantasmas" que somem)
        if s == "dodge" and self.ghosts_on and self._ghost_cd <= 0 and len(self.ghosts) < 5:
            self._ghost_cd = 0.045
            self.ghosts.append([self.pos.x, self.pos.y, 0.22, img.copy()])
        for gx, gy, life, gimg in self.ghosts:
            gsx, gsy = camera.to_screen(gx, gy)
            gimg.set_alpha(int(120 * life / 0.22))
            surf.blit(gimg, gimg.get_rect(midbottom=(gsx, gsy + 4)))

        # sombra
        surf.blit(_shadow(), (sx - 60, sy - 12))
        rect = img.get_rect(midbottom=(sx + dx * self.facing, sy + 4))
        if rect.width > 180:   # criaturas largas: frente do corpo fica na posição lógica, cauda para trás
            rect.centerx -= int(self.facing * (rect.width / 2 - 90))
        surf.blit(img, rect)

        # escudo / arco do golpe / telegraph
        front = sx + self.facing * 70
        if s == "block":
            shield = pygame.Rect(0, 0, 26, 120)
            shield.center = (front, sy - self.height * 0.5)
            pygame.draw.rect(surf, (120, 170, 255), shield, border_radius=10)
            pygame.draw.rect(surf, (230, 240, 255), shield, 3, border_radius=10)
        elif s == "strike":
            arc = pygame.Rect(0, 0, self.reach * 1.6, self.height * 0.9)
            arc.center = (sx + self.facing * self.reach * 0.35, sy - self.height * 0.5)
            start, end = (-1.2, 1.2) if self.facing > 0 else (math.pi - 1.2, math.pi + 1.2)
            col = (255, 90, 70) if self.attack and self.attack.unblockable else (255, 250, 220)
            pygame.draw.arc(surf, col, arc, start, end, 8)
        elif s == "windup" and self.attack:
            k = min(1.0, t / self.attack.windup)
            col = (255, 70, 60) if self.attack.unblockable else (255, 255, 255)
            cx, cy = int(sx), int(sy - self.height - 30)
            pygame.draw.circle(surf, col, (cx, cy), int(10 + 14 * k), 3)
            mark = font.render("!!" if self.attack.unblockable else "!", True, col)
            surf.blit(mark, mark.get_rect(center=(cx, cy)))
        elif s == "stunned":
            for i in range(3):
                a = self.anim_t * 5 + i * 2.1
                pygame.draw.circle(surf, (255, 230, 90),
                                   (int(sx + math.cos(a) * 34), int(sy - self.height - 12 + math.sin(a) * 8)), 6)
