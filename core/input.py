"""Input abstrato: o jogo só conhece AÇÕES ("left", "attack"...), nunca teclas.

Fontes suportadas nativamente:
  * Teclado  -> bindings configuráveis em assets/data/game.json
  * Mouse    -> ponteiro unificado
  * Toque    -> ponteiro unificado + swipe (vira ação direcional) + botões virtuais
Assim, portar para mobile = só ligar os botões virtuais; a lógica não muda.
"""
from dataclasses import dataclass, field

import pygame

DIRECTIONS = ("left", "right", "up", "down")


@dataclass
class Pointer:
    """Clique ou toque, em coordenadas lógicas."""
    id: int
    pos: tuple[float, float]
    start: tuple[float, float]
    start_time: float
    touch: bool


@dataclass
class VirtualButton:
    action: str
    rect: pygame.Rect
    label: str = ""
    held_by: set = field(default_factory=set)


class InputManager:
    SWIPE_MIN_DIST = 60      # px lógicos
    SWIPE_MAX_TIME = 0.35    # s
    TAP_MAX_DIST = 24        # px lógicos

    def __init__(self, display, bindings: dict[str, list[str]]) -> None:
        self.display = display
        self._key_to_actions: dict[int, list[str]] = {}
        for action, keys in bindings.items():
            for name in keys:
                code = pygame.key.key_code(name)
                self._key_to_actions.setdefault(code, []).append(action)
        self._held: set[str] = set()
        self._pressed: set[str] = set()
        self._released: set[str] = set()
        self.pointers: dict[int, Pointer] = {}
        self.taps: list[tuple[float, float]] = []          # cliques/toques curtos neste frame
        self.pointer_pos: tuple[float, float] = (0, 0)
        self.touch_mode = False                            # último input foi toque?
        self.virtual_buttons: list[VirtualButton] = []
        self.quit_requested = False
        self.text_input: list[str] = []
        self.wheel = 0                                     # rolagem do mouse neste frame
        self.drag_delta = pygame.Vector2()                 # arrasto do ponteiro neste frame
        self._time = 0.0

    # --- API de consulta ------------------------------------------------------------
    def pressed(self, action: str) -> bool:
        return action in self._pressed

    def held(self, action: str) -> bool:
        return action in self._held

    def released(self, action: str) -> bool:
        return action in self._released

    def pressed_direction(self) -> str | None:
        for d in DIRECTIONS:
            if d in self._pressed:
                return d
        return None

    def held_direction(self) -> str | None:
        for d in DIRECTIONS:
            if d in self._held:
                return d
        return None

    # --- botões virtuais (mobile) ---------------------------------------------------
    def set_virtual_buttons(self, buttons: list[VirtualButton]) -> None:
        for b in self.virtual_buttons:
            if b.held_by:
                self._release(b.action)
        self.virtual_buttons = buttons

    def draw_virtual_buttons(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.touch_mode:
            return
        for b in self.virtual_buttons:
            alpha = 150 if b.held_by else 70
            s = pygame.Surface(b.rect.size, pygame.SRCALPHA)
            pygame.draw.rect(s, (255, 255, 255, alpha), s.get_rect(), border_radius=18)
            surf.blit(s, b.rect)
            if b.label:
                t = font.render(b.label, True, (20, 20, 30))
                surf.blit(t, t.get_rect(center=b.rect.center))

    # --- ciclo por frame ------------------------------------------------------------
    def begin_frame(self, now: float) -> None:
        self._time = now
        self._pressed.clear()
        self._released.clear()
        self.taps.clear()
        self.text_input.clear()
        self.wheel = 0
        self.drag_delta.update(0, 0)

    def consume_step(self) -> None:
        """Eventos de um frame só valem no 1º passo de lógica (o loop pode dar vários)."""
        self._pressed.clear()
        self._released.clear()
        self.taps.clear()
        self.wheel = 0
        self.drag_delta.update(0, 0)

    def _press(self, action: str) -> None:
        if action not in self._held:
            self._pressed.add(action)
        self._held.add(action)

    def _release(self, action: str) -> None:
        if action in self._held:
            self._held.discard(action)
            self._released.add(action)

    def _pulse(self, action: str) -> None:
        """Ação instantânea (swipe): pressionada e solta no mesmo frame."""
        self._pressed.add(action)
        self._released.add(action)

    def _pointer_down(self, pid: int, pos, touch: bool) -> None:
        self.touch_mode = touch
        self.pointer_pos = pos
        for b in self.virtual_buttons:
            if touch and b.rect.collidepoint(pos):
                b.held_by.add(pid)
                self._press(b.action)
                return  # toque consumido pelo botão
        self.pointers[pid] = Pointer(pid, pos, pos, self._time, touch)
        self._press("pointer")

    def _pointer_move(self, pid: int, pos) -> None:
        self.pointer_pos = pos
        if pid in self.pointers:
            old = self.pointers[pid].pos
            self.drag_delta += (pos[0] - old[0], pos[1] - old[1])
            self.pointers[pid].pos = pos

    def _pointer_up(self, pid: int, pos) -> None:
        for b in self.virtual_buttons:
            if pid in b.held_by:
                b.held_by.discard(pid)
                if not b.held_by:
                    self._release(b.action)
                return
        p = self.pointers.pop(pid, None)
        if not self.pointers:
            self._release("pointer")
        if p is None:
            return
        dx, dy = pos[0] - p.start[0], pos[1] - p.start[1]
        dt = self._time - p.start_time
        dist = max(abs(dx), abs(dy))
        if dt <= self.SWIPE_MAX_TIME and dist >= self.SWIPE_MIN_DIST:
            if abs(dx) > abs(dy):
                self._pulse("right" if dx > 0 else "left")
            else:
                self._pulse("down" if dy > 0 else "up")
        elif dist < self.TAP_MAX_DIST:
            self.taps.append(pos)
        # senão foi um "arrasto" (scroll), tratado via drag_delta

    def process(self, event: pygame.event.Event) -> None:
        t = event.type
        if t == pygame.QUIT:
            self.quit_requested = True
        elif t == pygame.KEYDOWN:
            self.touch_mode = False
            for a in self._key_to_actions.get(event.key, ()):
                self._press(a)
        elif t == pygame.KEYUP:
            for a in self._key_to_actions.get(event.key, ()):
                self._release(a)
        elif t == pygame.TEXTINPUT:
            self.text_input.append(event.text)
        elif t == pygame.MOUSEBUTTONDOWN and event.button == 1 and not getattr(event, "touch", False):
            self._pointer_down(-1, event.pos, False)
        elif t == pygame.MOUSEBUTTONUP and event.button == 1 and not getattr(event, "touch", False):
            self._pointer_up(-1, event.pos)
        elif t == pygame.MOUSEMOTION and not getattr(event, "touch", False):
            self._pointer_move(-1, event.pos)
        elif t == pygame.MOUSEWHEEL:
            self.wheel += event.y
        elif t == pygame.FINGERDOWN:
            self._pointer_down(event.finger_id, self.display.normalized_to_virtual(event.x, event.y), True)
        elif t == pygame.FINGERMOTION:
            self._pointer_move(event.finger_id, self.display.normalized_to_virtual(event.x, event.y))
        elif t == pygame.FINGERUP:
            self._pointer_up(event.finger_id, self.display.normalized_to_virtual(event.x, event.y))
        elif t == pygame.WINDOWFOCUSLOST:
            for a in list(self._held):
                self._release(a)
