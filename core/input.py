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

_PRETTY = {"mouse1": "MOUSE ESQ.", "mouse2": "MOUSE DIR.", "mouse3": "MOUSE MEIO", "left shift": "SHIFT",
           "right shift": "SHIFT DIR.", "left ctrl": "CTRL", "right ctrl": "CTRL DIR.", "return": "ENTER",
           "space": "ESPAÇO", "left": "SETA ESQ.", "right": "SETA DIR.", "up": "SETA CIMA", "down": "SETA BAIXO",
           "escape": "ESC", "backspace": "BACKSPACE", "tab": "TAB"}


def pretty_key(name: str) -> str:
    """Nome legível de uma tecla/botão para mostrar ao jogador ("left shift" -> "SHIFT")."""
    return _PRETTY.get(name, name.upper())


def _mouse_button(name: str) -> int | None:
    """"mouse1" -> 1 (botão esquerdo). Outros nomes -> None (são teclas)."""
    if name.startswith("mouse") and name[5:].isdigit():
        return int(name[5:])
    return None

# Gamepad (layout Xbox/SDL): A confirma/ataca, B esquiva, X defende, Y ataca, LB defende, RB esquiva, Start/Back voltam.
GAMEPAD_BUTTONS = {0: ("confirm", "attack"), 1: ("dodge",), 2: ("block",), 3: ("attack",), 4: ("block",),
                   5: ("dodge",), 6: ("back",), 7: ("back",)}
STICK_DEADZONE = 0.5


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
    TAP_MAX_DIST = 24        # px lógicos (toque)
    CLICK_MAX_DIST = 48      # px lógicos (mouse: clique com a mão levemente "escorregando" ainda vale)

    def __init__(self, display, bindings: dict[str, list[str]]) -> None:
        self.display = display
        self._key_to_actions: dict[int, list[str]] = {}
        self._mouse_to_actions: dict[int, list[str]] = {}
        self.origin_x = 0                    # deslocamento da cena atual (layout fixo centralizado na janela larga)
        self.moved = False                   # o mouse se mexeu neste frame (foco por hover)
        self.mouse_seen = False              # já houve movimento/clique de mouse (liga o hover visual)
        self.bindings: dict[str, list[str]] = {}
        self._pads: dict[int, "pygame.joystick.JoystickType"] = {}    # mantém os controles vivos
        self._pad_dirs: dict[str, set[str]] = {"hat": set(), "stick": set()}
        self.capture = False                 # True: próxima tecla vira `captured` (tela de rebind)
        self.captured: str | None = None
        self.set_bindings(bindings)
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

    def set_bindings(self, bindings: dict[str, list[str]]) -> None:
        """(Re)monta o mapa tecla -> ações. Nome de tecla inválido é ignorado, nunca derruba o jogo."""
        self.bindings = {a: list(k) for a, k in bindings.items()}
        self._key_to_actions = {}
        self._mouse_to_actions = {}
        for action, keys in self.bindings.items():
            for name in keys:
                btn = _mouse_button(name)
                if btn is not None:
                    self._mouse_to_actions.setdefault(btn, []).append(action)
                    continue
                try:
                    code = pygame.key.key_code(name)
                except ValueError:
                    print(f"[input] tecla inválida ignorada: {name!r} ({action})")
                    continue
                self._key_to_actions.setdefault(code, []).append(action)

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
    def set_time(self, now: float) -> None:
        self._time = now

    def begin_frame(self, now: float) -> None:
        """Início de frame "completo": marca o tempo e descarta as entradas pendentes (usado em testes)."""
        self._time = now
        self.consume_step()

    def consume_step(self) -> None:
        """Descarta as entradas de "evento" (pressed/released/taps...). O loop do jogo chama isto DEPOIS de um
        passo de lógica ter visto as entradas; se o frame não teve passo (renderização mais rápida que os 60 Hz
        da lógica), elas ficam para o próximo frame — antes eram perdidas, e o clique/tecla "não pegava"."""
        self._pressed.clear()
        self._released.clear()
        self.taps.clear()
        self.text_input.clear()
        self.moved = False
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

    def _pos(self, pos) -> tuple[float, float]:
        """Posição do mouse (pixels da janela) convertida para as coordenadas da cena atual."""
        conv = getattr(self.display, "window_to_virtual", None)
        x, y = conv(*pos) if conv else pos
        return (x - self.origin_x, y)

    def _touch_pos(self, nx: float, ny: float) -> tuple[float, float]:
        x, y = self.display.normalized_to_virtual(nx, ny)
        return (x - self.origin_x, y)

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
        if not p.touch:
            if dist <= self.CLICK_MAX_DIST:
                self.taps.append(pos)
            return
        if dt <= self.SWIPE_MAX_TIME and dist >= self.SWIPE_MIN_DIST:
            if abs(dx) > abs(dy):
                self._pulse("right" if dx > 0 else "left")
            else:
                self._pulse("down" if dy > 0 else "up")
        elif dist < self.TAP_MAX_DIST:
            self.taps.append(pos)
        # senão foi um "arrasto" (scroll), tratado via drag_delta

    def _pad_update_dirs(self, source: str, dirs: set[str]) -> None:
        """Direções do controle (hat e analógico) viram as mesmas ações do teclado."""
        before = set().union(*self._pad_dirs.values())
        self._pad_dirs[source] = dirs
        after = set().union(*self._pad_dirs.values())
        for d in after - before:
            self._press(d)
        for d in before - after:
            self._release(d)

    def _process_pad(self, event: pygame.event.Event) -> bool:
        t = event.type
        if t == pygame.JOYDEVICEADDED:
            try:
                pad = pygame.joystick.Joystick(event.device_index)
                self._pads[pad.get_instance_id()] = pad
            except pygame.error:
                pass
        elif t == pygame.JOYDEVICEREMOVED:
            self._pads.pop(getattr(event, "instance_id", -1), None)
            self._pad_update_dirs("hat", set())
            self._pad_update_dirs("stick", set())
        elif t in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            self.touch_mode = False
            for a in GAMEPAD_BUTTONS.get(event.button, ()):
                (self._press if t == pygame.JOYBUTTONDOWN else self._release)(a)
        elif t == pygame.JOYHATMOTION:
            self.touch_mode = False
            x, y = event.value
            self._pad_update_dirs("hat", {d for d, on in (("left", x < 0), ("right", x > 0), ("up", y > 0), ("down", y < 0)) if on})
        elif t == pygame.JOYAXISMOTION and event.axis in (0, 1):
            cur = {d for d in self._pad_dirs["stick"]}
            if event.axis == 0:
                cur -= {"left", "right"}
                if abs(event.value) > STICK_DEADZONE:
                    cur.add("right" if event.value > 0 else "left")
            else:
                cur -= {"up", "down"}
                if abs(event.value) > STICK_DEADZONE:
                    cur.add("down" if event.value > 0 else "up")
            self._pad_update_dirs("stick", cur)
        else:
            return False
        return True

    def process(self, event: pygame.event.Event) -> None:
        t = event.type
        if self._process_pad(event):
            return
        if t == pygame.QUIT:
            self.quit_requested = True
        elif t == pygame.KEYDOWN:
            self.touch_mode = False
            if self.capture:
                self.captured = pygame.key.name(event.key)
                return
            for a in self._key_to_actions.get(event.key, ()):
                self._press(a)
        elif t == pygame.KEYUP:
            for a in self._key_to_actions.get(event.key, ()):
                self._release(a)
        elif t == pygame.TEXTINPUT:
            self.text_input.append(event.text)
        elif t == pygame.MOUSEBUTTONDOWN and not getattr(event, "touch", False):
            if self.capture:                      # tela de rebind: o botão do mouse vira a tecla
                self.captured = f"mouse{event.button}"
                return
            for a in self._mouse_to_actions.get(event.button, ()):
                self._press(a)
            if event.button == 1:
                self.mouse_seen = True
                self._pointer_down(-1, self._pos(event.pos), False)
        elif t == pygame.MOUSEBUTTONUP and not getattr(event, "touch", False):
            for a in self._mouse_to_actions.get(event.button, ()):
                self._release(a)
            if event.button == 1:
                self._pointer_up(-1, self._pos(event.pos))
        elif t == pygame.MOUSEMOTION and not getattr(event, "touch", False):
            self.moved = self.mouse_seen = True
            self._pointer_move(-1, self._pos(event.pos))
        elif t == pygame.MOUSEWHEEL:
            self.wheel += event.y
        elif t == pygame.FINGERDOWN:
            self._pointer_down(event.finger_id, self._touch_pos(event.x, event.y), True)
        elif t == pygame.FINGERMOTION:
            self._pointer_move(event.finger_id, self._touch_pos(event.x, event.y))
        elif t == pygame.FINGERUP:
            self._pointer_up(event.finger_id, self._touch_pos(event.x, event.y))
        elif t == pygame.WINDOWFOCUSLOST:
            for a in list(self._held):
                self._release(a)
