"""Culling por câmera + particionamento espacial (spatial hash grid).

Só o que intersecta o viewport é atualizado/desenhado. O grid deixa a consulta
O(células visíveis) em vez de O(todos os objetos) — escala para cenários grandes.
"""
from typing import Generic, Hashable, Iterable, TypeVar

import pygame

from core import compat

T = TypeVar("T", bound=Hashable)


class Camera:
    def __init__(self, width: int, height: int, world: pygame.Rect | None = None) -> None:
        self.view = compat.FRect(0, 0, width, height)
        self.world = world
        self.smooth = 8.0
        self.shake_time = 0.0
        self.shake_power = 0.0
        self._offset = pygame.Vector2()

    def follow(self, x: float, y: float, dt: float) -> None:
        tx, ty = x - self.view.w / 2, y - self.view.h / 2
        k = min(1.0, self.smooth * dt)
        self.view.x += (tx - self.view.x) * k
        self.view.y += (ty - self.view.y) * k
        if self.world:
            self.view.clamp_ip(self.world)

    def shake(self, power: float, time: float = 0.2) -> None:
        self.shake_power, self.shake_time = max(self.shake_power, power), max(self.shake_time, time)

    def update(self, dt: float) -> None:
        import random
        if self.shake_time > 0:
            self.shake_time -= dt
            p = self.shake_power * max(self.shake_time, 0) / 0.2
            self._offset.update(random.uniform(-p, p), random.uniform(-p, p))
        else:
            self._offset.update(0, 0)
            self.shake_power = 0

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x - self.view.x + self._offset.x, y - self.view.y + self._offset.y

    def visible(self, rect, margin: float = 0) -> bool:
        return self.view.inflate(margin * 2, margin * 2).colliderect(rect)


class SpatialGrid(Generic[T]):
    def __init__(self, cell: int = 256) -> None:
        self.cell = cell
        self._cells: dict[tuple[int, int], set[T]] = {}
        self._where: dict[T, tuple[tuple[int, int], ...]] = {}
        self._rects: dict[T, compat.FRect] = {}

    def _keys(self, r) -> tuple[tuple[int, int], ...]:
        c = self.cell
        x0, y0 = int(r.left // c), int(r.top // c)
        x1, y1 = int(r.right // c), int(r.bottom // c)
        return tuple((x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))

    def insert(self, obj: T, rect) -> None:
        self.remove(obj)
        keys = self._keys(rect)
        for k in keys:
            self._cells.setdefault(k, set()).add(obj)
        self._where[obj] = keys
        self._rects[obj] = compat.FRect(rect)

    def move(self, obj: T, rect) -> None:
        keys = self._keys(rect)
        if self._where.get(obj) != keys:
            self.insert(obj, rect)
        else:
            self._rects[obj] = compat.FRect(rect)

    def remove(self, obj: T) -> None:
        for k in self._where.pop(obj, ()):
            cell = self._cells.get(k)
            if cell:
                cell.discard(obj)
                if not cell:
                    del self._cells[k]
        self._rects.pop(obj, None)

    def query(self, rect) -> list[T]:
        seen: set[T] = set()
        out: list[T] = []
        for k in self._keys(rect):
            for obj in self._cells.get(k, ()):
                if obj not in seen and self._rects[obj].colliderect(rect):
                    seen.add(obj)
                    out.append(obj)
        return out

    def __len__(self) -> int:
        return len(self._where)

    def extend(self, items: Iterable[tuple[T, pygame.Rect]]) -> None:
        for obj, r in items:
            self.insert(obj, r)
