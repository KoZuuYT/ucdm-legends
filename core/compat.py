"""Compatibilidade entre pygame-ce (desktop) e pygame comum (Android via python-for-android).

O jogo usa `pygame.FRect` (retângulo de ponto flutuante, só existe no pygame-ce). Em pygame comum usamos
uma implementação mínima em Python com a parte da API que o jogo precisa."""
import pygame


class _FRectFallback:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, *args) -> None:
        if len(args) == 1:
            a = args[0]
            args = tuple(a) if not hasattr(a, "x") or isinstance(a, (tuple, list)) else (a.x, a.y, a.w, a.h)
        if len(args) == 2:
            (x, y), (w, h) = args
        else:
            x, y, w, h = args
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)

    # --- aliases ---
    width = property(lambda s: s.w, lambda s, v: setattr(s, "w", float(v)))
    height = property(lambda s: s.h, lambda s, v: setattr(s, "h", float(v)))
    left = property(lambda s: s.x, lambda s, v: setattr(s, "x", float(v)))
    top = property(lambda s: s.y, lambda s, v: setattr(s, "y", float(v)))
    right = property(lambda s: s.x + s.w, lambda s, v: setattr(s, "x", float(v) - s.w))
    bottom = property(lambda s: s.y + s.h, lambda s, v: setattr(s, "y", float(v) - s.h))
    centerx = property(lambda s: s.x + s.w / 2, lambda s, v: setattr(s, "x", float(v) - s.w / 2))
    centery = property(lambda s: s.y + s.h / 2, lambda s, v: setattr(s, "y", float(v) - s.h / 2))

    @property
    def center(self) -> tuple[float, float]:
        return (self.centerx, self.centery)

    @center.setter
    def center(self, v) -> None:
        self.centerx, self.centery = v

    @property
    def size(self) -> tuple[float, float]:
        return (self.w, self.h)

    def copy(self) -> "_FRectFallback":
        return _FRectFallback(self.x, self.y, self.w, self.h)

    def inflate(self, dx: float, dy: float) -> "_FRectFallback":
        return _FRectFallback(self.x - dx / 2, self.y - dy / 2, self.w + dx, self.h + dy)

    def move(self, dx: float, dy: float) -> "_FRectFallback":
        return _FRectFallback(self.x + dx, self.y + dy, self.w, self.h)

    def colliderect(self, other) -> bool:
        ox, oy, ow, oh = (other.x, other.y, other.w, other.h) if hasattr(other, "w") else tuple(other)
        return self.x < ox + ow and ox < self.x + self.w and self.y < oy + oh and oy < self.y + self.h

    def collidepoint(self, *p) -> bool:
        px, py = p[0] if len(p) == 1 else p
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def clamp_ip(self, other) -> None:
        ox, oy, ow, oh = (other.x, other.y, other.w, other.h) if hasattr(other, "w") else tuple(other)
        self.x = ox + (ow - self.w) / 2 if self.w > ow else min(max(self.x, ox), ox + ow - self.w)
        self.y = oy + (oh - self.h) / 2 if self.h > oh else min(max(self.y, oy), oy + oh - self.h)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def __repr__(self) -> str:
        return f"FRect({self.x}, {self.y}, {self.w}, {self.h})"


FRect = getattr(pygame, "FRect", _FRectFallback)
