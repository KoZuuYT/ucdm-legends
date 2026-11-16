"""Cenas + gerenciador em pilha (push/pop/replace) com fade entre cenas.

Cada módulo de conteúdo (menu, hub, treino, arena) é uma Scene independente.
Cenas por baixo da pilha podem continuar sendo desenhadas (overlays/pausa).
"""
from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from core.engine import Game


class Scene:
    #: se True, a cena de baixo ainda é desenhada (útil para pop-ups/pausa)
    transparent = False

    def __init__(self, game: "Game") -> None:
        self.game = game

    # ciclo de vida
    def enter(self) -> None: ...
    def exit(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...

    # loop
    def update(self, dt: float) -> None: ...
    def draw(self, surf: pygame.Surface) -> None: ...


class SceneManager:
    FADE_TIME = 0.18

    def __init__(self) -> None:
        self.stack: list[Scene] = []
        self._pending: list[Callable[[], None]] = []
        self._fade = 0.0          # 0..1 opacidade do preto
        self._fade_dir = 0        # +1 escurecendo, -1 clareando
        self._fade_cb: Callable[[], None] | None = None
        self._overlay: pygame.Surface | None = None

    @property
    def current(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    # --- operações (aplicadas fora do update para evitar mutação durante iteração) ---
    def push(self, scene: Scene, fade: bool = False) -> None:
        self._queue(lambda: self._do_push(scene), fade)

    def pop(self, fade: bool = False) -> None:
        self._queue(self._do_pop, fade)

    def replace(self, scene: Scene, fade: bool = True) -> None:
        self._queue(lambda: (self._do_pop(), self._do_push(scene)), fade)

    def reset(self, scene: Scene, fade: bool = True) -> None:
        def go():
            while self.stack:
                self._do_pop()
            self._do_push(scene)
        self._queue(go, fade)

    def _queue(self, op: Callable[[], None], fade: bool) -> None:
        if fade:
            self._fade_dir, self._fade_cb = 1, op
        else:
            self._pending.append(op)

    def _do_push(self, scene: Scene) -> None:
        if self.current:
            self.current.pause()
        self.stack.append(scene)
        scene.enter()

    def _do_pop(self) -> None:
        if self.stack:
            self.stack.pop().exit()
            if self.current:
                self.current.resume()

    # --- loop -----------------------------------------------------------------------
    def update(self, dt: float) -> None:
        while self._pending:
            self._pending.pop(0)()
        if self._fade_dir:
            self._fade += self._fade_dir * dt / self.FADE_TIME
            if self._fade >= 1 and self._fade_dir > 0:
                self._fade, self._fade_dir = 1.0, -1
                cb, self._fade_cb = self._fade_cb, None
                if cb:
                    cb()
            elif self._fade <= 0 and self._fade_dir < 0:
                self._fade, self._fade_dir = 0.0, 0
            return  # congela gameplay durante a transição
        if self.current:
            self.current.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        # desenha a partir da cena opaca mais alta
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].transparent:
            start -= 1
        for scene in self.stack[max(start, 0):]:
            scene.draw(surf)
        if self._fade > 0:
            if self._overlay is None or self._overlay.get_size() != surf.get_size():
                self._overlay = pygame.Surface(surf.get_size())
            self._overlay.set_alpha(int(255 * min(self._fade, 1)))
            surf.blit(self._overlay, (0, 0))
