"""Perfil do jogador: atributos treináveis, XP, ouro, arma e progresso na arena.

Todas as curvas vêm de assets/data/balance.json."""
from dataclasses import dataclass, field

from core import config

STATS = ("strength", "defense", "agility", "focus")


def xp_to_next(level: int) -> int:
    curve = config.load("balance")["xp_curve"]
    return int(curve["base"] * curve["growth"] ** (level - 1))


def weapon_cost(level: int) -> int:
    w = config.load("balance")["weapon"]
    return int(w["base_cost"] * w["growth"] ** (level - 1))


@dataclass
class StatProgress:
    level: int = 1
    xp: int = 0

    def add_xp(self, amount: int) -> int:
        """Adiciona XP e devolve quantos níveis subiu."""
        self.xp += max(0, int(amount))
        gained = 0
        while self.xp >= xp_to_next(self.level):
            self.xp -= xp_to_next(self.level)
            self.level += 1
            gained += 1
        return gained


@dataclass
class Profile:
    character: str = "steve"            # id da aparência (skin) do jogador; o lutador é sempre o Steve
    collection: dict[str, int] = field(default_factory=dict)   # lendas UCDM derrotadas -> vezes
    achievements: list[str] = field(default_factory=list)      # ids das conquistas liberadas
    history: list[str] = field(default_factory=list)           # últimas lutas: "W" (vitória) / "L" (derrota)
    skins_seen: list[str] = field(default_factory=lambda: ["steve"])   # aparências já anunciadas como desbloqueadas
    gold: int = 0
    weapon_level: int = 1
    arena_stage: int = 0                # índice do próximo inimigo
    wins: int = 0
    best_scores: dict[str, int] = field(default_factory=dict)
    playtime: float = 0.0               # segundos jogados neste save
    name: str = ""                      # nome do treinador (opcional, renomeável no seletor de saves)
    seen_help: bool = False             # já viu o tutorial inicial?
    last_training: str = ""             # último treino jogado ("Treinar de novo" no hub)
    counters: dict[str, int] = field(default_factory=dict)   # estatísticas do treinador
    stats: dict[str, StatProgress] = field(default_factory=lambda: {s: StatProgress() for s in STATS})

    def level(self, stat: str) -> int:
        return self.stats[stat].level

    def bump(self, key: str, n: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + n

    def record(self, key: str, value: int) -> None:
        """Guarda o maior valor visto (ex.: maior golpe)."""
        if value > self.counters.get(key, 0):
            self.counters[key] = value

    def legends(self) -> int:
        """Quantas lendas de raridade Lendária já foram derrotadas."""
        from entities import roster
        return sum(1 for cid in self.collection if roster.rarity(cid) == "lendario")

    def total_level(self) -> int:
        return sum(s.level for s in self.stats.values()) - len(STATS) + 1

    def to_dict(self) -> dict:
        return {
            "character": self.character, "gold": self.gold, "weapon_level": self.weapon_level,
            "arena_stage": self.arena_stage, "wins": self.wins, "best_scores": self.best_scores,
            "playtime": round(self.playtime, 1), "name": self.name, "seen_help": self.seen_help, "last_training": self.last_training,
            "counters": self.counters, "collection": self.collection, "skins_seen": self.skins_seen, "achievements": self.achievements, "history": self.history[-20:],
            "stats": {k: {"level": v.level, "xp": v.xp} for k, v in self.stats.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        skin_ids = {s["id"] for s in config.load("skins")["skins"]}
        who = d.get("character", "steve")
        p = cls(character=who if who in skin_ids else "steve",   # saves antigos (lutador UCDM) viram Steve
                gold=d.get("gold", 0),
                weapon_level=d.get("weapon_level", 1), arena_stage=d.get("arena_stage", 0),
                wins=d.get("wins", 0), best_scores=d.get("best_scores", {}),
                playtime=float(d.get("playtime", 0.0)), name=str(d.get("name", ""))[:16],
                seen_help=bool(d.get("seen_help", False)), last_training=str(d.get("last_training", "")), counters=dict(d.get("counters", {})),
                collection={str(k): int(v) for k, v in dict(d.get("collection", {})).items()},
                skins_seen=[str(x) for x in d.get("skins_seen", ["steve"])],
                achievements=[str(x) for x in d.get("achievements", [])],
                history=[str(x) for x in d.get("history", []) if x in ("W", "L")][-20:])
        for k in STATS:
            s = d.get("stats", {}).get(k, {})
            p.stats[k] = StatProgress(s.get("level", 1), s.get("xp", 0))
        return p
