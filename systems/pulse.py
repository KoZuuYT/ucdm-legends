"""Pulso no ritmo da música: valor que "bate" a cada tempo (BPM). Usado no logo do menu e em brilhos de UI."""
import math

DEFAULT_BPM = 96.0


def beat(t: float, bpm: float = DEFAULT_BPM) -> float:
    """1.0 no instante da batida, decaindo rápido até 0 antes da próxima."""
    phase = (t * bpm / 60.0) % 1.0
    return math.exp(-phase * 7.0)


def phase(t: float, bpm: float = DEFAULT_BPM) -> float:
    return (t * bpm / 60.0) % 1.0
