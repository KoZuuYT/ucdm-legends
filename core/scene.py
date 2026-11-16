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

    def on_focus_lost(self) -> None:
        """A janela perdeu o foco (cenas de jogo abrem a pausa aqui)."""


class SceneManager:
    FADE_TIME = 0.18
    #: duração relativa por tipo de transição ("fade" é o padrão; True == "fade")
    KINDS = {"fade": 1.0, "slide": 1.5, "iris": 1.8}

    def __init__(self) -> None:
        self.stack: list[Scene] = []
        self._pending: list[Callable[[], None]] = []
        self._fade = 0.0          # 0..1 opacidade do preto
        self._fade_dir = 0        # +1 escurecendo, -1 clareando
        self._fade_cb: Callable[[], None] | None = None
        self._kind = "fade"
        self._overlay: pygame.Surface | None = None

    @property
    def current(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    # --- operações (aplicadas fora do update para evitar mutação durante iteração) ---
    def push(self, scene: Scene, fade: "bool | str" = False) -> None:
        self._queue(lambda: self._do_push(scene), fade)

    def pop(self, fade: "bool | str" = False) -> None:
        self._queue(self._do_pop, fade)

    def replace(self, scene: Scene, fade: "bool | str" = True) -> None:
        self._queue(lambda: (self._do_pop(), self._do_push(scene)), fade)

    def reset(self, scene: Scene, fade: "bool | str" = True) -> None:
        def go():
            while self.stack:
                self._do_pop()
            self._do_push(scene)
        self._queue(go, fade)

    def _queue(self, op: Callable[[], None], fade: "bool | str") -> None:
        if fade:
            self._kind = fade if isinstance(fade, str) and fade in self.KINDS else "fade"
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

    def flush(self) -> None:
        """Aplica já as operações pendentes (sem fade)."""
        while self._pending:
            self._pending.pop(0)()

    @property
    def busy(self) -> bool:
        """Há troca de cena enfileirada ou em andamento?"""
        return bool(self._pending) or self._fade_dir != 0

    # --- loop -----------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.flush()
        if self._fade_dir:
            self._fade += self._fade_dir * dt / (self.FADE_TIME * self.KINDS[self._kind])
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
            self._draw_transition(surf, min(self._fade, 1.0))

    def _draw_transition(self, surf: pygame.Surface, k: float) -> None:
        w, h = surf.get_size()
        if self._kind == "slide":
            # cortina que entra pela esquerda e sai pela direita
            bw = int(w * k)
            surf.fill((0, 0, 0), (0, 0, bw, h) if self._fade_dir > 0 else (w - bw, 0, bw, h))
        elif self._kind == "iris":
            if self._overlay is None or self._overlay.get_size() != (w, h):
                self._overlay = pygame.Surface((w, h))
            self._overlay.set_colorkey((255, 0, 255))
            self._overlay.set_alpha(255)
            self._overlay.fill((0, 0, 0))
            radius = int((1 - k) * (w * 0.62))
            if radius > 0:
                pygame.draw.circle(self._overlay, (255, 0, 255), (w // 2, h // 2), radius)
            surf.blit(self._overlay, (0, 0))
        else:
            if self._overlay is None or self._overlay.get_size() != (w, h):
                self._overlay = pygame.Surface((w, h))
            self._overlay.set_colorkey(None)
            self._overlay.fill((0, 0, 0))
            self._overlay.set_alpha(int(255 * k))
            surf.blit(self._overlay, (0, 0))
