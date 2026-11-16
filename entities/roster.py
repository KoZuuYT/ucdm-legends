"""Elenco de personagens + fábricas de lutadores a partir dos dados JSON."""
from core import config
from entities.fighter import AttackDef, Fighter
from entities.progression import Profile


def characters() -> list[dict]:
    return config.load("characters")["characters"]


def character(cid: str) -> dict:
    for c in characters():
        if c["id"] == cid:
            return c
    return {"id": cid, "name": cid, "sprite": f"sprites/characters/{cid}.png", "faces": -1}


def enemies() -> list[dict]:
    return config.load("enemies")["enemies"]


def build_player(profile: Profile, x: float, y: float) -> Fighter:
    f = config.load("balance")["fighter"]
    w = config.load("balance")["weapon"]
    st, de, ag, fo = (profile.level(s) - 1 for s in ("strength", "defense", "agility", "focus"))
    ch = character(profile.character)
    return Fighter(
        ch["name"], ch["sprite"], x, y,
        hp=f["base_hp"] + f["hp_per_defense"] * de,
        damage=f["base_damage"] + f["damage_per_strength"] * st + w["damage_per_level"] * (profile.weapon_level - 1),
        stamina=f["base_stamina"] + f["stamina_per_agility"] * ag,
        stamina_regen=f["stamina_regen"] + f["regen_per_agility"] * ag,
        block_reduction=min(f["block_reduction_max"], f["block_reduction"] + f["block_reduction_per_defense"] * de),
        parry_window=min(f["parry_window_max"], f["parry_window"] + f["parry_window_per_focus"] * fo),
        crit_chance=min(f["crit_max"], f["crit_chance"] + f["crit_per_focus"] * fo),
        crit_mult=f["crit_mult"],
        dodge_cost=max(f["dodge_cost_min"], f["dodge_cost"] + f["dodge_cost_per_agility"] * ag),
        attacks=[AttackDef.from_cfg(a) for a in f["attacks"]],
        facing=1, sprite_faces=ch.get("faces", -1),
    )


def build_enemy(edef: dict, x: float, y: float) -> Fighter:
    f = config.load("balance")["fighter"]
    ch = character(edef["character"])
    return Fighter(
        ch["name"], ch["sprite"], x, y,
        hp=edef["hp"], damage=edef["damage"], stamina=edef.get("stamina", 100),
        stamina_regen=edef.get("stamina_regen", f["stamina_regen"]),
        block_reduction=edef.get("block_reduction", 0.6), parry_window=0.0,
        crit_chance=edef.get("crit_chance", 0.05), crit_mult=f["crit_mult"],
        dodge_cost=edef.get("dodge_cost", 25),
        attacks=[AttackDef.from_cfg(a) for a in edef["attacks"]],
        facing=-1, reach=edef.get("reach", 190), height=edef.get("height", 230),
        sprite_faces=ch.get("faces", -1), stagger_resist=edef.get("stagger_resist", 0.3),
    )
