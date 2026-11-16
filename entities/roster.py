"""Elenco de personagens + fábricas de lutadores a partir dos dados JSON."""
from core import config
from entities.fighter import AttackDef, Fighter
from entities.progression import Profile


def characters() -> list[dict]:
    return config.load("characters")["characters"]


def skins() -> list[dict]:
    """Aparências do jogador (Steve e skins desbloqueáveis)."""
    return config.load("skins")["skins"]


def skin(sid: str) -> dict:
    for s in skins():
        if s["id"] == sid:
            return {**s, "faces": 1}
    return {**skins()[0], "faces": 1}


def character(cid: str) -> dict:
    for s in skins():
        if s["id"] == cid:
            return {**s, "faces": 1}
    for c in characters():
        if c["id"] == cid:
            return c
    return {"id": cid, "name": cid, "sprite": f"sprites/characters/{cid}.png", "faces": -1}


# --- raridades e desafios ------------------------------------------------------------
def rarity_order() -> list[str]:
    return config.load("rarity")["order"]


def rarity(cid: str) -> str:
    for c in characters():
        if c["id"] == cid:
            return c.get("rarity", "comum")
    return "comum"


def rarity_info(name: str) -> dict:
    return config.load("rarity")["tiers"][name]


def rarity_color(name: str) -> tuple:
    return tuple(rarity_info(name)["color"])


def tier_unlocked(profile: Profile, name: str) -> bool:
    """Um nível de raridade abre quando a escada da arena chega ao estágio exigido."""
    return profile.arena_stage >= rarity_info(name)["unlock_stage"]


def challenge_edef(cid: str) -> dict:
    """Definição de inimigo para um desafio de lenda: copia um molde da escada conforme a raridade."""
    import copy
    import hashlib
    r = rarity(cid)
    info = rarity_info(r)
    ladder = enemies()
    h = int(hashlib.md5(cid.encode()).hexdigest(), 16)
    idx = min(len(ladder) - 1, info["templates"][h % len(info["templates"])])
    e = copy.deepcopy(ladder[idx])
    s = info["scale"]
    # pequena variação determinística (±8%) para os personagens da mesma raridade não serem idênticos
    v = 0.92 + (h >> 8) % 17 / 100
    e["id"] = f"challenge_{cid}"
    e["character"] = cid
    e["title"] = info["label"]
    e["hp"] = max(30, round(e["hp"] * s * v))
    e["damage"] = max(1, round(e["damage"] * s * (2 - v)))
    e["poise"] = float(e.get("poise", e["hp"] * 0.45)) * s
    e["gold"] = info["gold"]
    e["challenge"] = True
    return e


def unlocked_skin(profile: Profile, s: dict) -> bool:
    u = s.get("unlock", {})
    if "wins" in u and profile.wins < u["wins"]:
        return False
    if "stage" in u and profile.arena_stage < u["stage"]:
        return False
    if "collection" in u and len(profile.collection) < u["collection"]:
        return False
    if "legend" in u and profile.legends() < u["legend"]:
        return False
    return True


def skin_requirement(s: dict) -> str:
    u = s.get("unlock", {})
    if "wins" in u:
        return f"Vença {u['wins']} lutas"
    if "stage" in u:
        return f"Chegue à luta {u['stage'] + 1} da arena" if u["stage"] < len(enemies()) else "Vença o chefe da arena"
    if "collection" in u:
        return f"Derrote {u['collection']} lendas diferentes"
    if "legend" in u:
        return "Derrote uma lenda Lendária"
    return ""


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
    fighter = Fighter(
        ch["name"], ch["sprite"], x, y,
        hp=edef["hp"], damage=edef["damage"], stamina=edef.get("stamina", 100),
        stamina_regen=edef.get("stamina_regen", f["stamina_regen"]),
        block_reduction=edef.get("block_reduction", 0.6), parry_window=edef.get("ai", {}).get("parry_window", 0.0),
        crit_chance=edef.get("crit_chance", 0.05), crit_mult=f["crit_mult"],
        dodge_cost=edef.get("dodge_cost", 25),
        attacks=[AttackDef.from_cfg(a) for a in edef["attacks"]],
        facing=-1, reach=edef.get("reach", 190), height=edef.get("height", 230),
        sprite_faces=ch.get("faces", -1), stagger_resist=edef.get("stagger_resist", 0.3),
    )
    fighter.max_poise = fighter.poise = float(edef.get("poise", edef["hp"] * 0.45))
    fighter.armor = float(edef.get("armor", 0.45))
    return fighter
