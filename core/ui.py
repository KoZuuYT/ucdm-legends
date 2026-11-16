"""Widgets mínimos de UI, navegáveis por teclado, mouse e toque."""
from typing import Callable

import pygame

from core.input import InputManager

WHITE = (240, 240, 240)
DARK = (22, 24, 34)
ACCENT = (255, 196, 64)
RED = (220, 70, 60)
GREEN = (90, 200, 110)
BLUE = (80, 150, 240)


def text(surf, font, msg, pos, color=WHITE, anchor="topleft", shadow=True):
    img = font.render(str(msg), True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(font.render(str(msg), True, (0, 0, 0)), rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def bar(surf, rect, frac, color, back=(40, 40, 50), border=WHITE):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=4)
    inner = rect.inflate(-4, -4)
    inner.width = int(inner.width * max(0.0, min(1.0, frac)))
    if inner.width > 0:
        pygame.draw.rect(surf, color, inner, border_radius=3)
    pygame.draw.rect(surf, border, rect, 2, border_radius=4)


def panel(surf, rect, color=(20, 22, 32, 210)):
    rect = pygame.Rect(rect)
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

    def draw(self, surf, font, focused=False, small_font=None):
        hover = self.rect.collidepoint(pygame.mouse.get_pos()) if pygame.display.get_init() else False
        base = (70, 74, 96) if self.enabled else (45, 45, 52)
        if (focused or hover) and self.enabled:
            base = (110, 100, 60)
        pygame.draw.rect(surf, base, self.rect, border_radius=10)
        pygame.draw.rect(surf, ACCENT if focused else (150, 150, 170), self.rect, 2, border_radius=10)
        cy = self.rect.centery - (9 if self.sub and small_font else 0)
        text(surf, font, self.label, (self.rect.centerx, cy), WHITE if self.enabled else (130, 130, 130), "center")
        if self.sub and small_font:
            text(surf, small_font, self.sub, (self.rect.centerx, self.rect.centery + 16), (200, 200, 170), "center")


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
        if inp.pressed("down"):
            self.focus = (self.focus + c) % n
        elif inp.pressed("up"):
            self.focus = (self.focus - c) % n
        elif inp.pressed("right") and c > 1:
            self.focus = (self.focus + 1) % n
        elif inp.pressed("left") and c > 1:
            self.focus = (self.focus - 1) % n
        if inp.pressed("confirm"):
            b = self.buttons[self.focus]
            if b.enabled:
                b.on_click()
                return
        for pos in inp.taps:
            for i, b in enumerate(self.buttons):
                if b.enabled and b.rect.collidepoint(pos):
                    self.focus = i
                    b.on_click()
                    return

    def draw(self, surf, font, small_font=None) -> None:
        for i, b in enumerate(self.buttons):
            b.draw(surf, font, i == self.focus, small_font)
