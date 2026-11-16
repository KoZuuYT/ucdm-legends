"""Resolução virtual fixa + escala adaptativa (letterbox) sem distorção.

O jogo inteiro desenha em uma superfície lógica (ex.: 1280x720). Usamos o
flag SCALED do SDL2, que faz o upscale na GPU e mantém o aspect ratio com
barras pretas — barato em CPU e idêntico em desktop e mobile.
"""
import pygame


class Display:
    def __init__(self, width: int, height: int, title: str, *, fullscreen: bool = False,
                 vsync: bool = True, headless: bool = False) -> None:
        self.width, self.height = width, height
        self.headless = headless
        self.fullscreen = bool(fullscreen and not headless)
        pygame.display.set_caption(title)
        if not headless:
            self._set_icon()
        flags = 0 if headless else (pygame.SCALED | pygame.RESIZABLE)
        if fullscreen and not headless:
            flags |= pygame.FULLSCREEN
        try:
            self.surface = pygame.display.set_mode((width, height), flags, vsync=int(vsync and not headless))
        except pygame.error:  # alguns drivers não aceitam vsync
            self.surface = pygame.display.set_mode((width, height), flags)
        self.rect = self.surface.get_rect()

    @staticmethod
    def _set_icon() -> None:
        from core import paths
        icon = paths.ASSETS_DIR / "sprites" / "ui" / "icon.png"
        try:
            if icon.is_file():
                pygame.display.set_icon(pygame.image.load(str(icon)))
        except pygame.error:
            pass

    # --- conversões de coordenadas ------------------------------------------------
    def window_size(self) -> tuple[int, int]:
        try:
            return pygame.display.get_window_size()
        except (AttributeError, pygame.error):
            return self.width, self.height

    def window_to_virtual(self, wx: float, wy: float) -> tuple[float, float]:
        """Converte pixels da janela física para coordenadas lógicas (considera letterbox)."""
        ww, wh = self.window_size()
        scale = min(ww / self.width, wh / self.height) or 1
        ox = (ww - self.width * scale) / 2
        oy = (wh - self.height * scale) / 2
        return (wx - ox) / scale, (wy - oy) / scale

    def normalized_to_virtual(self, nx: float, ny: float) -> tuple[float, float]:
        """Eventos de toque (FINGER*) vêm normalizados 0..1 em relação à janela."""
        ww, wh = self.window_size()
        return self.window_to_virtual(nx * ww, ny * wh)

    def toggle_fullscreen(self) -> None:
        if self.headless:
            return
        pygame.display.toggle_fullscreen()
        self.fullscreen = not self.fullscreen

    def present(self) -> None:
        pygame.display.flip()
