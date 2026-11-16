"""Curvas de interpolação (easing) e um Tween simples. t sempre em 0..1."""
import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def linear(t: float) -> float:
    return clamp01(t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out_sine(t: float) -> float:
    t = clamp01(t)
    return -(math.cos(math.pi * t) - 1) / 2


def ease_out_back(t: float) -> float:
    """Passa um pouco do alvo e volta (efeito 'pop')."""
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class Tween:
    """Valor que vai de a até b em `duration` segundos com uma curva."""

    def __init__(self, a: float, b: float, duration: float, ease=ease_out_cubic) -> None:
        self.a, self.b, self.duration, self.ease = a, b, max(duration, 1e-6), ease
        self.t = 0.0

    def update(self, dt: float) -> float:
        self.t = min(self.duration, self.t + dt)
        return self.value

    @property
    def value(self) -> float:
        return lerp(self.a, self.b, self.ease(self.t / self.duration))

    @property
    def done(self) -> bool:
        return self.t >= self.duration
