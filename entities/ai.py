"""IA de inimigos data-driven (parâmetros em assets/data/enemies.json -> ai).

O inimigo LÊ o jogador: se ele ataca em sequência (spam), a chance de defender sobe; defesas bem
cronometradas viram PARRY (atordoa o jogador) e um bloqueio costuma ser seguido de um contra-golpe (riposte).
Golpes em sequência (combo) e golpes especiais (!! imbloqueável, laranja quebra-guarda) exigem reagir, não só bater.
"""
import dataclasses
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
        self.parry_skill = cfg.get("parry_skill", 0.0)       # chance de cronometrar a defesa para dar PARRY
        self.read_spam = cfg.get("read_spam", 0.0)           # quanto o spam do jogador aumenta a chance de defender
        self.riposte = cfg.get("riposte", 0.0)               # chance de contra-golpe depois de defender
        self._cd = random.uniform(*self.cooldown)
        self._reacted_to: int | None = None
        self._block_hold = 0.0
        self._guard_at: float | None = None
        self._pressure: list[float] = []     # instantes em que o jogador começou a atacar (últimos 3 s)
        self._chain_left = 0
        self._chain_atk: AttackDef | None = None
        self._riposte_at: float | None = None
        self._last_special = False

    # --- escolha do golpe -----------------------------------------------------------------------
    def _pick_attack(self) -> AttackDef:
        atks = self.me.attacks
        weights = [a.weight * (0.35 if (self._last_special and (a.unblockable or a.guard_break)) else 1.0) for a in atks]
        return random.choices(atks, weights=weights)[0]

    def _start_attack(self, atk: AttackDef) -> bool:
        if self.me.attack_cmd(atk):
            self._last_special = atk.unblockable or atk.guard_break
            self._chain_left, self._chain_atk = atk.chain, atk
            self._cd = random.uniform(*self.cooldown)
            return True
        return False

    @property
    def pressure(self) -> int:
        return len(self._pressure)

    # --- eventos vindos da arena -------------------------------------------------------------------
    def on_defended(self, outcome: str, now: float) -> None:
        """O inimigo bloqueou/aparou/esquivou um golpe do jogador: chance de contra-golpe imediato."""
        chance = {"parry": min(1.0, self.riposte + 0.4), "block": self.riposte, "dodge": self.riposte * 0.7}.get(outcome, 0)
        if random.random() < chance:
            self._riposte_at = now + (0.1 if outcome == "parry" else 0.16)

    # --- ciclo ---------------------------------------------------------------------------------------
    def update(self, dt: float, now: float) -> None:
        me, foe = self.me, self.foe
        if me.state == "dead" or foe.state == "dead":
            me.set_block(False, now)
            return
        dist = abs(foe.pos.x - me.pos.x)
        me.facing = 1 if foe.pos.x > me.pos.x else -1
        if me.state in ("stunned", "hurt"):
            self._chain_left, self._guard_at, self._riposte_at = 0, None, None
        self._pressure = [t for t in self._pressure if now - t < 3.0]

        # Reação defensiva ao telegraph do jogador (uma vez por golpe).
        if foe.state == "windup" and self._reacted_to != id(foe.attack):
            self._reacted_to = id(foe.attack)
            self._pressure.append(now)
            spam = max(0, len(self._pressure) - 1)
            p_block = min(0.85, self.block_chance + self.read_spam * 0.2 * spam)
            p_dodge = min(0.5, self.dodge_chance + 0.02 * spam)
            if not me.busy:
                r = random.random()
                if r < p_dodge:
                    me.dodge()
                elif r < p_dodge + p_block:
                    wait = max(0.0, foe._windup_time() - me.parry_window * 0.6)
                    if me.parry_window > 0 and random.random() < self.parry_skill:
                        self._guard_at = now + wait                  # guarda "no tempo": pode virar PARRY
                        self._block_hold = wait + foe.attack.active + 0.25
                    else:
                        me.set_block(True, now)
                        self._block_hold = foe.attack.windup + foe.attack.active + 0.1
        if foe.state not in ("windup", "strike"):
            self._reacted_to = None

        if self._guard_at is not None and now >= self._guard_at:
            self._guard_at = None
            if not me.busy:
                me.set_block(True, now)

        if me.state == "block":
            self._block_hold -= dt
            if self._block_hold <= 0:
                me.set_block(False, now)
            return

        # Contra-golpe depois de defender / combo em sequência
        if self._riposte_at is not None and now >= self._riposte_at:
            self._riposte_at = None
            if not me.busy and dist <= me.reach * 1.15:
                self._start_attack(self._pick_attack())
                return
        if self._chain_left > 0 and me.state == "idle" and self._chain_atk is not None:
            if dist <= me.reach * 1.15:
                quick = dataclasses.replace(self._chain_atk, windup=self._chain_atk.windup * 0.7, chain=0)
                self._chain_left -= 1
                if not me.attack_cmd(quick):
                    self._chain_left = 0
                return
            self._chain_left = 0

        # Posicionamento
        want = me.reach * self.preferred
        if dist > want + 20:
            me.move(me.facing)
        elif dist < want * 0.5:
            me.move(-me.facing)

        # Ataque: acelera quando o jogador está vulnerável (recuperando golpe, atordoado ou sem estamina)
        rate = 0.5 + self.aggression
        if foe.state in ("recover", "stunned") or foe.stamina < 8:
            rate *= 2.2
        self._cd -= dt * rate
        if self._cd <= 0 and dist <= me.reach and not me.busy:
            self._start_attack(self._pick_attack())
