"""Widgets mínimos de UI, navegáveis por teclado, mouse e toque."""
from typing import Callable

import pygame

from core.i18n import tr
from core.input import InputManager

WHITE = (240, 240, 240)
DARK = (22, 24, 34)
ACCENT = (255, 196, 64)
RED = (220, 70, 60)
GREEN = (90, 200, 110)
BLUE = (80, 150, 240)

#: definido pelo Game: função(nome_do_som). Mantém a UI independente do sistema de áudio.
sound_hook: Callable[[str], None] | None = None


def sfx(name: str) -> None:
    if sound_hook:
        sound_hook(name)


# --- acessibilidade -------------------------------------------------------------------------
_DEFAULT_PALETTE = {"RED": RED, "GREEN": GREEN, "BLUE": BLUE}
_COLORBLIND = {"RED": (213, 94, 0), "GREEN": (86, 180, 233), "BLUE": (0, 114, 178)}      # Okabe-Ito
_STAT_CB = {"strength": (213, 94, 0), "defense": (0, 114, 178), "agility": (86, 180, 233), "focus": (240, 228, 66)}
high_contrast = False
colorblind = False


def apply_accessibility(*, colorblind_mode: bool, high_contrast_mode: bool) -> None:
    """Troca a paleta (vermelho/verde -> laranja/azul) e liga contorno/bordas mais fortes."""
    global RED, GREEN, BLUE, high_contrast, colorblind
    colorblind, high_contrast = bool(colorblind_mode), bool(high_contrast_mode)
    pal = _COLORBLIND if colorblind else _DEFAULT_PALETTE
    RED, GREEN, BLUE = pal["RED"], pal["GREEN"], pal["BLUE"]


def stat_color(stat: str, base) -> tuple:
    return _STAT_CB.get(stat, tuple(base)) if colorblind else tuple(base)


def _mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def text(surf, font, msg, pos, color=WHITE, anchor="topleft", shadow=True):
    msg = tr(msg) if isinstance(msg, str) else msg
    img = font.render(str(msg), True, color)
    rect = img.get_rect(**{anchor: pos})
    if high_contrast:       # contorno preto em volta: legível em qualquer fundo
        dark = font.render(str(msg), True, (0, 0, 0))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            surf.blit(dark, rect.move(dx, dy))
    elif shadow:
        surf.blit(font.render(str(msg), True, (0, 0, 0)), rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def bar(surf, rect, frac, color, back=(40, 40, 50), border=WHITE, ghost: float | None = None):
    """Barra de progresso. `ghost` (0..1) desenha a faixa clara que "escorre" depois de levar dano."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=4)
    inner = rect.inflate(-4, -4)
    if ghost is not None and ghost > frac:
        g = inner.copy()
        g.width = int(inner.width * max(0.0, min(1.0, ghost)))
        pygame.draw.rect(surf, (235, 235, 235), g, border_radius=3)
    inner.width = int(inner.width * max(0.0, min(1.0, frac)))
    if inner.width > 0:
        pygame.draw.rect(surf, color, inner, border_radius=3)
    pygame.draw.rect(surf, border, rect, 4 if high_contrast else 2, border_radius=4)


def panel(surf, rect, color=(20, 22, 32, 210)):
    rect = pygame.Rect(rect)
    if high_contrast:
        color = (*color[:3], 255)
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, color, s.get_rect(), border_radius=12)
    pygame.draw.rect(s, (255, 255, 255, 60), s.get_rect(), 2, border_radius=12)
    surf.blit(s, rect)


class Button:
    def __init__(self, rect, label: str, on_click: Callable[[], None], *, enabled=True, sub: str = ""):
        self.rect = pygame.Rect(rect)
        self.label, self.sub = label, sub
        self.on_click = on_click
        self.enabled = enabled
        self._k = 0.0        # 0..1: quanto o botão está "aceso" (suaviza hover/foco)
        self._pop = 0.0      # pulso ao clicar
        self._t = pygame.time.get_ticks() / 1000 if pygame.get_init() else 0.0

    def click(self) -> None:
        self._pop = 1.0
        self.on_click()

    def draw(self, surf, font, focused=False, small_font=None):
        now = pygame.time.get_ticks() / 1000
        dt = max(0.0, min(0.05, now - self._t))
        self._t = now
        hover = self.rect.collidepoint(pygame.mouse.get_pos()) if pygame.display.get_init() else False
        lit = (focused or hover) and self.enabled
        self._k += ((1.0 if lit else 0.0) - self._k) * min(1.0, dt * 14)
        self._pop = max(0.0, self._pop - dt * 5)
        k = self._k
        base = (70, 74, 96) if self.enabled else (45, 45, 52)
        base = _mix(base, (110, 100, 60), k) if self.enabled else base
        r = self.rect.inflate(int(10 * k + 8 * self._pop), int(4 * k + 4 * self._pop))
        if k > 0.05:   # brilho suave atrás do botão aceso
            glow = pygame.Surface((r.w + 16, r.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 196, 64, int(55 * k)), glow.get_rect(), border_radius=16)
            surf.blit(glow, glow.get_rect(center=r.center))
        pygame.draw.rect(surf, base, r, border_radius=10)
        pygame.draw.rect(surf, _mix((150, 150, 170), ACCENT, k) if self.enabled else (90, 90, 100), r, 2,
                         border_radius=10)
        cy = r.centery - (9 if self.sub and small_font else 0)
        text(surf, font, self.label, (r.centerx, cy), WHITE if self.enabled else (130, 130, 130), "center")
        if self.sub and small_font:
            text(surf, small_font, self.sub, (r.centerx, r.centery + 16), (200, 200, 170), "center")


class Menu:
    """Lista de botões com foco por teclado (setas/enter) e clique/toque."""

    def __init__(self, buttons: list[Button], columns: int = 1):
        self.buttons = buttons
        self.columns = columns
        self.focus = 0

    def update(self, inp: InputManager) -> None:
        if not self.buttons:
            return
        n, c = len(self.buttons), self.columns
        before = self.focus
        if inp.pressed("down"):
            self.focus = (self.focus + c) % n
        elif inp.pressed("up"):
            self.focus = (self.focus - c) % n
        elif inp.pressed("right") and c > 1:
            self.focus = (self.focus + 1) % n
        elif inp.pressed("left") and c > 1:
            self.focus = (self.focus - 1) % n
        if self.focus != before:
            sfx("hover")
        if inp.pressed("confirm"):
            b = self.buttons[self.focus]
            if b.enabled:
                sfx("confirm")
                b.click()
                return
        for pos in inp.taps:
            for i, b in enumerate(self.buttons):
                if b.enabled and b.rect.collidepoint(pos):
                    self.focus = i
                    sfx("click")
                    b.click()
                    return

    def draw(self, surf, font, small_font=None) -> None:
        for i, b in enumerate(self.buttons):
            b.draw(surf, font, i == self.focus, small_font)
