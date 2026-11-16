"""Nota (S-D) e dicas pós-luta, calculadas dos números da luta (função pura: fácil de testar).

Entrada `stats` (dict): won, time, par_time, hp_frac, taken, dealt, parries, perfect_dodges, dodges, breaks,
guardbreaks_taken, unblockable_taken, attacks, hits_landed, fatigue_peak.
"""

GRADES = ("D", "C", "B", "A", "S")
GRADE_COLORS = {"S": (255, 205, 70), "A": (120, 225, 140), "B": (110, 185, 255), "C": (200, 200, 210), "D": (200, 120, 110)}


def grade(stats: dict) -> str:
    """S-D conforme vida restante, ritmo e jogadas de reação (parry/esquiva perfeita). Derrota = 'D'."""
    if not stats.get("won"):
        return "D"
    hp = max(0.0, min(1.0, stats.get("hp_frac", 0.0)))
    par = max(1.0, stats.get("par_time", 40.0))
    pace = max(0.0, min(1.0, 1.4 - stats.get("time", par) / par))          # na meta = 0,4; muito rápido = 1
    style = min(1.0, (stats.get("parries", 0) * 1.0 + stats.get("perfect_dodges", 0) * 0.8) / 5.0)
    score = 0.5 * hp + 0.2 * pace + 0.3 * style
    for g, lim in (("S", 0.80), ("A", 0.62), ("B", 0.45), ("C", 0.30)):
        if score >= lim:
            return g
    return "D"


def hints(stats: dict, limit: int = 2) -> list[str]:
    """Até `limit` dicas úteis (as mais relevantes primeiro), sempre em português (a UI traduz)."""
    out: list[str] = []
    if stats.get("guardbreaks_taken", 0) >= 2:
        out.append("Golpes laranja quebram a guarda: apare no tempo certo ou esquive.")
    if stats.get("unblockable_taken", 0) >= 1:
        out.append("Golpes vermelhos (!!) não podem ser bloqueados: esquive.")
    attacks = stats.get("attacks", 0)
    if stats.get("fatigue_peak", 0) >= 3 or attacks >= 14 and stats.get("hits_landed", 0) < attacks * 0.5:
        out.append("Atacar sem parar cansa e reduz o dano: ataque e recue.")
    if stats.get("parries", 0) == 0 and stats.get("perfect_dodges", 0) == 0:
        out.append("Parry e esquiva no último instante abrem um contra-ataque crítico.")
    if stats.get("breaks", 0) == 0 and stats.get("won") is False:
        out.append("Quebre a armadura do inimigo com parry ou contra-ataque para causar dano cheio.")
    if stats.get("taken", 0) > 0 and stats.get("dodges", 0) == 0:
        out.append("Esquivar gasta estamina mas evita o dano por completo.")
    return out[:limit]
