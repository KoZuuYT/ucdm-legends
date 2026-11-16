"""Conquistas: definidas em assets/data/achievements.json, avaliadas a partir do perfil do jogador.

`check(profile)` desbloqueia o que ficou pronto e devolve as novas conquistas (para o toast/tela).
Recompensas são só cosméticas/orgulho: nada afeta o combate."""
from core import config


def defs() -> list[dict]:
    return config.load("achievements")["achievements"]


def value(profile, stat: str) -> int:
    """Valor atual de um critério (contador do perfil ou campo especial)."""
    if stat == "wins":
        return profile.wins
    if stat == "arena_stage":
        return profile.arena_stage
    if stat == "collection":
        return len(profile.collection)
    if stat == "legends":
        return profile.legends()
    if stat == "weapon_level":
        return profile.weapon_level
    if stat == "gold_total":
        return profile.counters.get("gold_total", 0)
    if stat == "skins":
        from entities import roster
        return sum(1 for s in roster.skins() if roster.unlocked_skin(profile, s))
    return profile.counters.get(stat, 0)


def progress(profile, d: dict) -> tuple[int, int]:
    return min(value(profile, d["stat"]), d["min"]), d["min"]


def unlocked(profile, d: dict) -> bool:
    return d["id"] in profile.achievements


def check(profile) -> list[dict]:
    """Libera as conquistas cujo critério foi atingido; devolve as recém-liberadas."""
    new = []
    for d in defs():
        if d["id"] in profile.achievements:
            continue
        if value(profile, d["stat"]) >= d["min"]:
            profile.achievements.append(d["id"])
            new.append(d)
    return new


def announce(game, new: list[dict]) -> None:
    """Toast dourado para cada conquista nova (fila do feedback) e som de recompensa."""
    for d in new:
        game.feedback.toast(f"Conquista: {d['name']}", (255, 205, 70), 4.0)
    if new:
        game.audio.play("coin")
