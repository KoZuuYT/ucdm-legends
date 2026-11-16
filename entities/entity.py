"""Base de entidades: posição + componentes plugáveis.

Componentes são objetos simples guardados por tipo; sistemas consultam
`entity.get(Tipo)`. Isso permite adicionar comportamentos (ex.: Burn, Shield,
AI nova) sem mexer na hierarquia de classes."""
import itertools
from typing import TypeVar

import pygame

from core import compat

C = TypeVar("C")
_ids = itertools.count(1)


class Entity:
    def __init__(self, x: float = 0, y: float = 0, w: float = 64, h: float = 64) -> None:
        self.id = next(_ids)
        self.pos = pygame.Vector2(x, y)    # pés (centro-base) da entidade
        self.size = pygame.Vector2(w, h)
        self.alive = True
        self._components: dict[type, object] = {}

    @property
    def rect(self) -> compat.FRect:
        return compat.FRect(self.pos.x - self.size.x / 2, self.pos.y - self.size.y, self.size.x, self.size.y)

    def add(self, component: C) -> C:
        self._components[type(component)] = component
        return component

    def get(self, kind: type[C]) -> C | None:
        return self._components.get(kind)  # type: ignore[return-value]

    def has(self, kind: type) -> bool:
        return kind in self._components

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other) -> bool:
        return self is other
