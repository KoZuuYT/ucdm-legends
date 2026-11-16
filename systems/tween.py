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


# --- curvas extras (linguagem de movimento, plano 02) ----------------------------------------------
def ease_in_cubic(t: float) -> float:
    t = clamp01(t)
    return t ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_quint(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 5


def ease_out_bounce(t: float) -> float:
    t = clamp01(t)
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def ease_out_elastic(t: float) -> float:
    t = clamp01(t)
    if t in (0.0, 1.0):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


EASES = {"linear": linear, "out": ease_out_cubic, "in": ease_in_cubic, "in_out": ease_in_out_cubic,
         "back": ease_out_back, "bounce": ease_out_bounce, "elastic": ease_out_elastic, "quint": ease_out_quint}


def stagger(index: int, step: float = 0.04) -> float:
    """Atraso (s) do item `index` numa entrada em cascata."""
    return index * step


def staged(t: float, index: int, duration: float = 0.22, step: float = 0.04, ease=ease_out_cubic) -> float:
    """Progresso 0..1 do item `index` quando a cascata começou há `t` segundos."""
    return ease((t - stagger(index, step)) / max(duration, 1e-6))


class Spring:
    """Mola criticamente amortecida: segue um alvo sem depender de tempo fixo (cursor, barras, câmera de menu)."""

    def __init__(self, value: float = 0.0, stiffness: float = 220.0, damping: float | None = None) -> None:
        self.value = self.target = float(value)
        self.vel = 0.0
        self.k = stiffness
        self.c = damping if damping is not None else 2 * math.sqrt(stiffness)

    def update(self, dt: float) -> float:
        dt = min(dt, 1 / 30)                 # passos grandes não explodem a simulação
        acc = self.k * (self.target - self.value) - self.c * self.vel
        self.vel += acc * dt
        self.value += self.vel * dt
        return self.value

    def snap(self, value: float) -> None:
        self.value = self.target = float(value)
        self.vel = 0.0

    @property
    def settled(self) -> bool:
        return abs(self.target - self.value) < 0.01 and abs(self.vel) < 0.05


class Seq:
    """Sequência de etapas (atraso, duração, função(progresso 0..1)). Útil para introduções/resultados."""

    def __init__(self) -> None:
        self.steps: list[tuple[float, float, object, object]] = []
        self.t = 0.0

    def at(self, start: float, duration: float, fn, ease=linear) -> "Seq":
        self.steps.append((start, max(duration, 1e-6), fn, ease))
        return self

    @property
    def length(self) -> float:
        return max((s + d for s, d, _, _ in self.steps), default=0.0)

    def update(self, dt: float) -> bool:
        """Avança e chama cada etapa ativa; devolve True quando terminou."""
        self.t += dt
        for start, dur, fn, ease in self.steps:
            if self.t >= start:
                fn(ease((self.t - start) / dur))
        return self.t >= self.length

    def skip(self) -> None:
        self.update(max(0.0, self.length - self.t))
