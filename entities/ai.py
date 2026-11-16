"""IA de inimigos data-driven (parâmetros em assets/data/enemies.json -> ai)."""
import random

from entities.fighter import AttackDef, Fighter


class EnemyBrain:
    def __init__(self, me: Fighter, foe: Fighter, cfg: dict) -> None:
        self.me, self.foe = me, foe
        self.aggression = cfg.get("aggression", 0.5)         # 0..1: frequência de ataques
        self.block_chance = cfg.get("block_chance", 0.25)    # reação ao windup do jogador
        self.dodge_chance = cfg.get("dodge_chance", 0.1)
        self.cooldown = cfg.get("cooldown", [0.8, 1.8])
        self.preferred = cfg.get("preferred_distance", 0.85)  # fração do alcance
        self._cd = random.uniform(*self.cooldown)
        self._reacted_to: int | None = None
        self._block_hold = 0.0

    def _pick_attack(self) -> AttackDef:
        atks = self.me.attacks
        return random.choices(atks, weights=[a.weight for a in atks])[0]

    def update(self, dt: float, now: float) -> None:
        me, foe = self.me, self.foe
        if me.state == "dead" or foe.state == "dead":
            me.set_block(False, now)
            return
        dist = abs(foe.pos.x - me.pos.x)
        me.facing = 1 if foe.pos.x > me.pos.x else -1

        # Reação defensiva ao telegraph do jogador (uma vez por golpe).
        if foe.state == "windup" and self._reacted_to != id(foe.attack):
            self._reacted_to = id(foe.attack)
            r = random.random()
            if r < self.dodge_chance:
                me.dodge()
            elif r < self.dodge_chance + self.block_chance:
                me.set_block(True, now)
                self._block_hold = foe.attack.windup + foe.attack.active + 0.1
        if foe.state not in ("windup", "strike"):
            self._reacted_to = None

        if me.state == "block":
            self._block_hold -= dt
            if self._block_hold <= 0:
                me.set_block(False, now)
            return

        # Posicionamento
        want = me.reach * self.preferred
        if dist > want + 20:
            me.move(me.facing)
        elif dist < want * 0.5:
            me.move(-me.facing)

        # Ataque
        self._cd -= dt * (0.5 + self.aggression)
        if self._cd <= 0 and dist <= me.reach and not me.busy:
            if me.attack_cmd(self._pick_attack()):
                self._cd = random.uniform(*self.cooldown)
