"""Janela redimensionável sem barras pretas.

O jogo é desenhado num "canvas" de altura fixa (720) e largura que acompanha a proporção da janela
(de 1280 até 1920 de largura lógica). O canvas é escalado para a janela inteira. Cenas "wide" (arena, menu)
usam o canvas todo; as demais têm layout fixo 1280x720 centralizado e as laterais são preenchidas
esticando a borda da cena (ver SceneManager). Se a janela for MAIS estreita que 16:9, sobram faixas em
cima/embaixo, também preenchidas esticando a borda, em vez de preto.
"""
import pygame

BASE_W, BASE_H = 1280, 720      # tamanho de projeto: todas as cenas de layout fixo usam isto
MAX_W = 1920                    # maior largura lógica (21:9 ≈ 1680; além de ~2,67:1 sobram laterais esticadas)


class Display:
    def __init__(self, width: int, height: int, title: str, *, fullscreen: bool = False,
                 vsync: bool = True, headless: bool = False) -> None:
        self.width, self.height = width, height          # tamanho de PROJETO (fixo)
        self.canvas_w = width                            # largura lógica atual do canvas (dinâmica)
        self.headless = headless
        self.fullscreen = False
        self.vsync = vsync
        self.scale = 1.0
        self.offset = (0, 0)                             # canto superior esquerdo do canvas dentro da janela
        self.dest_size = (width, height)
        self._windowed_size = (width, height)
        pygame.display.set_caption(title)
        if not headless:
            self._set_icon()
        from core import paths
        if paths.ANDROID and not headless:        # celular: tela inteira, sem janela
            self.window = self._set_mode((0, 0), pygame.FULLSCREEN)
            self.fullscreen = True
        else:
            self.window = self._set_mode((width, height), pygame.RESIZABLE)
        self.surface = self._new_canvas(width)
        self.rect = self.surface.get_rect()
        if fullscreen and not headless and not self.fullscreen:
            self.toggle_fullscreen()
        self.layout()

    # --- janela / canvas -------------------------------------------------------------------
    def _set_mode(self, size, flags) -> pygame.Surface:
        # NÃO passar vsync=: em janela comum (sem SCALED/OpenGL) ele não faz efeito e, no Windows, trocar de
        # tela cheia para janela depois de desenhar derruba o processo (segfault dentro do set_mode).
        if self.headless:
            return pygame.display.set_mode(size)
        return pygame.display.set_mode(size, flags)

    def _new_canvas(self, w: int) -> pygame.Surface:
        s = pygame.Surface((w, self.height))
        return s.convert() if pygame.display.get_surface() else s

    def window_size(self) -> tuple[int, int]:
        try:
            surf = pygame.display.get_surface()
            return surf.get_size() if surf else (self.width, self.height)
        except pygame.error:
            return self.width, self.height

    def layout(self) -> bool:
        """Recalcula a largura lógica e a escala conforme o tamanho atual da janela. True se o canvas mudou."""
        ww, wh = self.window_size()
        ww, wh = max(1, ww), max(1, wh)
        aspect = ww / wh
        cw = int(round(self.height * aspect))
        cw = max(self.width, min(MAX_W, cw))            # nunca mais estreito que o projeto (1280)
        changed = cw != self.canvas_w
        if changed:
            self.canvas_w = cw
            self.surface = self._new_canvas(cw)
            self.rect = self.surface.get_rect()
        self.scale = min(ww / cw, wh / self.height)
        dw, dh = max(1, round(cw * self.scale)), max(1, round(self.height * self.scale))
        self.dest_size = (dw, dh)
        self.offset = ((ww - dw) // 2, (wh - dh) // 2)
        return changed

    def toggle_fullscreen(self) -> None:
        if self.headless:
            return
        if not self.fullscreen:
            self._windowed_size = self.window_size()
            self.window = self._set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = self._set_mode(self._windowed_size, pygame.RESIZABLE)
        self.fullscreen = not self.fullscreen
        self.layout()

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
    def window_to_virtual(self, wx: float, wy: float) -> tuple[float, float]:
        """Pixels da janela -> coordenadas do canvas (considera escala e faixas)."""
        if self.headless:
            return wx, wy
        s = self.scale or 1.0
        return (wx - self.offset[0]) / s, (wy - self.offset[1]) / s

    def normalized_to_virtual(self, nx: float, ny: float) -> tuple[float, float]:
        """Eventos de toque (FINGER*) vêm normalizados 0..1 em relação à janela."""
        ww, wh = self.window_size()
        return self.window_to_virtual(nx * ww, ny * wh)

    # --- apresentação --------------------------------------------------------------
    def present(self) -> None:
        if self.headless:
            pygame.display.flip()
            return
        win = pygame.display.get_surface()
        if win is None:
            return
        dw, dh = self.dest_size
        ox, oy = self.offset
        if (dw, dh) == self.surface.get_size() and (ox, oy) == (0, 0) and win.get_size() == (dw, dh):
            win.blit(self.surface, (0, 0))
        else:
            dest = win.subsurface((ox, oy, dw, dh))
            if self.scale >= 2.5:                      # telas enormes: escala simples (mais barata)
                pygame.transform.scale(self.surface, (dw, dh), dest)
            else:
                pygame.transform.smoothscale(self.surface, (dw, dh), dest)
            self._fill_bars(win, ox, oy, dw, dh)
        pygame.display.flip()

    @staticmethod
    def _fill_bars(win: pygame.Surface, ox: int, oy: int, dw: int, dh: int) -> None:
        """Sobras (janela com proporção diferente do canvas): estica a borda da imagem em vez de deixar preto."""
        ww, wh = win.get_size()
        if ox > 0:
            pygame.transform.scale(win.subsurface((ox, oy, 1, dh)), (ox, dh), win.subsurface((0, oy, ox, dh)))
            rw = ww - ox - dw
            if rw > 0:
                pygame.transform.scale(win.subsurface((ox + dw - 1, oy, 1, dh)), (rw, dh),
                                       win.subsurface((ox + dw, oy, rw, dh)))
        if oy > 0:
            pygame.transform.scale(win.subsurface((0, oy, ww, 1)), (ww, oy), win.subsurface((0, 0, ww, oy)))
            bh = wh - oy - dh
            if bh > 0:
                pygame.transform.scale(win.subsurface((0, oy + dh - 1, ww, 1)), (ww, bh),
                                       win.subsurface((0, oy + dh, ww, bh)))
