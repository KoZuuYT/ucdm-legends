"""Widgets de UI: botões animados (hover, clique, brilho "glint"), painéis, barras e textos de título.

Tudo é navegável por teclado, mouse e toque. Os desenhos pesados (gradientes, painéis) ficam em cache por tamanho,
então o custo por frame é baixo.
"""
import math
from typing import Callable

import pygame

from core import mcui, theme
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
#: ponteiro atual (coordenadas da cena), atualizado pelo Game a cada frame: (x, y, mouse_ativo, botão_apertado)
pointer: tuple[float, float, bool, bool] = (-999.0, -999.0, False, False)


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


# --- caches de desenho ------------------------------------------------------------------------
_cache: dict = {}


def _remember(key, make):
    s = _cache.get(key)
    if s is None:
        if len(_cache) > 160:
            _cache.clear()
        s = _cache[key] = make()
    return s


def gradient_surface(size, top, bottom, radius: int = 0, alpha: int = 255) -> pygame.Surface:
    """Retângulo com degradê vertical (e cantos arredondados), em cache."""
    w, h = max(1, int(size[0])), max(1, int(size[1]))

    def make():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            k = y / max(1, h - 1)
            c = _mix(top[:3], bottom[:3], k)
            pygame.draw.line(s, (*c, alpha), (0, y), (w, y))
        if radius:
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return s
    return _remember(("grad", w, h, tuple(top[:3]), tuple(bottom[:3]), radius, alpha), make)


# --- texto -------------------------------------------------------------------------------------
def _heading(font, msg: str, color) -> pygame.Surface:
    """Texto de título: degradê claro->cor + contorno escuro (fontes grandes)."""
    def make():
        body = font.render(msg, True, (255, 255, 255))
        w, h = body.get_size()
        grad = gradient_surface((w, h), _mix(color, (255, 255, 255), 0.55), _mix(color, (0, 0, 0), 0.12))
        body = body.copy()
        body.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        out = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        edge = font.render(msg, True, (14, 14, 22))
        for dx in (0, 2, 4, 6, 8):
            for dy in (0, 2, 4, 6, 8):
                if (dx, dy) != (4, 4):
                    out.blit(edge, (dx, dy))
        out.blit(body, (4, 4))
        return out
    return _remember(("head", font.get_height(), font.get_bold(), msg, tuple(color)), make)


def text(surf, font, msg, pos, color=WHITE, anchor="topleft", shadow=True):
    msg = tr(msg) if isinstance(msg, str) else msg
    if isinstance(msg, str) and font.get_height() >= 40 and shadow and not high_contrast:
        img = _heading(font, msg, color)
        rect = img.get_rect(**{anchor: pos})
        surf.blit(img, rect)
        return rect.inflate(-8, -8)
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


# --- fundo animado dos menus ------------------------------------------------------------------
_BLOBS = ((0.12, 0.25, 260, (70, 60, 140)), (0.85, 0.2, 300, (140, 80, 60)), (0.5, 0.95, 340, (50, 100, 150)),
          (0.92, 0.8, 220, (90, 60, 130)))


def _blob(radius: int, color) -> pygame.Surface:
    def make():
        s = pygame.Surface((radius * 2, radius * 2))
        for i in range(radius, 0, -6):
            k = (1 - i / radius) ** 2
            pygame.draw.circle(s, tuple(int(c * k * 0.5) for c in color), (radius, radius), i)
        return s
    return _remember(("blob", radius, tuple(color)), make)


def backdrop(surf, t: float, animate: bool = True) -> None:
    """Fundo dos menus: degradê escuro com manchas de cor à deriva e uma grade fina (barato: tudo pré-renderizado)."""
    w, h = surf.get_size()
    surf.blit(gradient_surface((w, h), (30, 32, 54), (12, 13, 22)), (0, 0))
    for i, (fx, fy, r, col) in enumerate(_BLOBS):
        dx = math.sin(t * 0.17 + i * 1.7) * 50 if animate else 0
        dy = math.cos(t * 0.13 + i * 2.3) * 36 if animate else 0
        b = _blob(r, col)
        surf.blit(b, (fx * w + dx - r, fy * h + dy - r), special_flags=pygame.BLEND_RGB_ADD)
    off = int(t * 8) % 64 if animate else 0
    for x in range(-64 + off, w, 64):
        pygame.draw.line(surf, (30, 33, 50), (x, 0), (x, h))


def row(surf, rect, focused: bool = False, active: bool = False) -> None:
    """Linha de lista (opções etc.): degradê escuro; dourada e com brilho quando focada."""
    rect = pygame.Rect(rect)
    if focused:
        top, bot, edge = (96, 82, 44), (58, 48, 26), ACCENT
        surf.blit(_remember(("rowglow", rect.w, rect.h), lambda: _glow_surface(rect.size)), (rect.x - 18, rect.y - 18))
    elif active:
        top, bot, edge = (66, 62, 46), (44, 42, 34), (150, 140, 90)
    else:
        top, bot, edge = (44, 47, 68), (30, 32, 48), (74, 78, 104)
    surf.blit(gradient_surface(rect.size, top, bot, radius=10), rect)
    pygame.draw.rect(surf, edge, rect, 2 if focused else 1, border_radius=10)


def wrap_text(font, msg: str, width: int) -> list[str]:
    """Quebra o texto (já traduzido por quem chama) em linhas que cabem em `width` pixels."""
    words, lines, cur = msg.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.size(trial)[0] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# --- barras e painéis ---------------------------------------------------------------------------
def bar(surf, rect, frac, color, back=(34, 36, 48), border=WHITE, ghost: float | None = None, rtl: bool = False):
    """Barra de progresso com brilho. `ghost` (0..1) desenha a faixa clara que "escorre" depois de levar dano.
    `rtl` preenche da direita para a esquerda (barra do inimigo)."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=5)
    inner = rect.inflate(-4, -4)
    full = inner.width

    def span(f):
        r = inner.copy()
        r.width = int(full * max(0.0, min(1.0, f)))
        if rtl:
            r.right = inner.right
        return r
    if ghost is not None and ghost > frac:
        pygame.draw.rect(surf, (235, 235, 235), span(ghost), border_radius=4)
    inner = span(frac)
    if inner.width > 0:
        fill = gradient_surface(inner.size, _mix(color, (255, 255, 255), 0.35), _mix(color, (0, 0, 0), 0.3), radius=4)
        surf.blit(fill, inner)
        if inner.height >= 8:                     # faixa de brilho no topo
            gloss = pygame.Surface((inner.width, max(2, inner.height // 3)), pygame.SRCALPHA)
            gloss.fill((255, 255, 255, 46))
            surf.blit(gloss, (inner.x, inner.y + 1))
    pygame.draw.rect(surf, border, rect, 4 if high_contrast else 2, border_radius=5)


def panel(surf, rect, color=(20, 22, 32, 210), accent=True):
    """Painel com degradê, sombra suave, borda e cantos em destaque."""
    rect = pygame.Rect(rect)
    if theme.mc() and not high_contrast and mcui.panel(surf, rect):
        return
    alpha = 255 if high_contrast else color[3] if len(color) > 3 else 210
    base = color[:3]
    shadow = _remember(("pshadow", rect.w, rect.h), lambda: _shadow_surface(rect.size))
    surf.blit(shadow, (rect.x - 10, rect.y - 4))
    body = gradient_surface(rect.size, _mix(base, (255, 255, 255), 0.10), _mix(base, (0, 0, 0), 0.25), radius=14,
                            alpha=alpha)
    surf.blit(body, rect)
    pygame.draw.rect(surf, (120, 124, 150), rect, 2, border_radius=14)
    if accent:
        c = ACCENT
        for sx, sy, dx, dy in ((rect.left, rect.top, 1, 1), (rect.right - 1, rect.top, -1, 1),
                               (rect.left, rect.bottom - 1, 1, -1), (rect.right - 1, rect.bottom - 1, -1, -1)):
            pygame.draw.line(surf, c, (sx + dx * 6, sy + dy * 2), (sx + dx * 22, sy + dy * 2), 3)
            pygame.draw.line(surf, c, (sx + dx * 2, sy + dy * 6), (sx + dx * 2, sy + dy * 22), 3)


def _shadow_surface(size) -> pygame.Surface:
    w, h = size
    s = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
    for i, a in enumerate((18, 14, 10, 6)):
        pygame.draw.rect(s, (0, 0, 0, a), (10 - 8 + i * 2, 12 - 8 + i * 2, w + 16 - i * 4, h + 16 - i * 4),
                         border_radius=18)
    return s


# --- botões ------------------------------------------------------------------------------------
_SHEEN_W = 46


def _now() -> float:
    """Relógio da UI (segundos). Trocável em testes para animar sem esperar."""
    return pygame.time.get_ticks() / 1000


def _sheen() -> pygame.Surface:
    """Faixa diagonal de luz (o "glint") que atravessa o botão."""
    def make():
        h = 80
        s = pygame.Surface((_SHEEN_W + h // 2, h), pygame.SRCALPHA)
        for y in range(h):
            off = (h - y) // 2                      # inclinação
            for x in range(_SHEEN_W):
                edge = 1 - abs(x - _SHEEN_W / 2) / (_SHEEN_W / 2)
                s.set_at((x + off, y), (255, 255, 255, int(80 * edge * edge)))
        return s
    return _remember(("sheen",), make)


class Button:
    def __init__(self, rect, label: str, on_click: Callable[[], None], *, enabled=True, sub: str = ""):
        self.rect = pygame.Rect(rect)
        self.label, self.sub = label, sub
        self.on_click = on_click
        self.enabled = enabled
        self._k = 0.0               # 0..1: quanto o botão está "aceso" (suaviza hover/foco)
        self._pop = 0.0             # pulso ao clicar
        self._press = 0.0           # 0..1: botão do mouse segurado em cima dele
        self._glint = -1.0          # progresso do brilho (0..1); <0 = parado
        self._ripple: tuple[tuple[float, float], float] | None = None
        self._lit_before = False
        self._t = _now() if pygame.get_init() else 0.0

    def click(self, pos=None) -> None:
        self._pop = 1.0
        self._glint = 0.0
        self._ripple = (pos if pos is not None else self.rect.center, 0.0)
        self.on_click()

    def hovered(self) -> bool:
        px, py, active, _ = pointer
        return active and self.enabled and self.rect.collidepoint(px, py)

    def draw(self, surf, font, focused=False, small_font=None):
        now = _now()
        dt = max(0.0, min(0.05, now - self._t))
        self._t = now
        hover = self.hovered()
        lit = (focused or hover) and self.enabled
        pressed = hover and pointer[3]
        self._k += ((1.0 if lit else 0.0) - self._k) * min(1.0, dt * 14)
        self._press += ((1.0 if pressed else 0.0) - self._press) * min(1.0, dt * 22)
        self._pop = max(0.0, self._pop - dt * 4.5)
        if lit and not self._lit_before:         # acabou de acender: brilho passa uma vez
            self._glint = 0.0
        self._lit_before = lit
        if self._glint >= 0:
            self._glint += dt * 1.5
            if self._glint > 1.15:
                self._glint = 0.0 if lit and (now * 0.7) % 3.0 < 0.06 else -1.0   # lit: repete de vez em quando
        k = self._k
        pop = math.sin(min(1.0, self._pop) * math.pi) * 0.5 if self._pop else 0.0
        grow_x = 12 * k + 14 * pop - 8 * self._press
        grow_y = 6 * k + 8 * pop - 5 * self._press
        r = self.rect.inflate(int(grow_x), int(grow_y))
        if theme.mc() and not high_contrast:
            return self._draw_mc(surf, r, font, small_font, lit, dt)
        if self.enabled:
            top = _mix((92, 98, 130), (168, 138, 66), k)
            bot = _mix((50, 54, 82), (104, 82, 36), k)
            edge = _mix((150, 154, 180), ACCENT, k)
            txt = WHITE
        else:
            top, bot, edge, txt = (62, 63, 72), (40, 41, 48), (82, 82, 92), (130, 130, 136)
        # sombra + brilho externo
        shadow = _remember(("bshadow", r.w, r.h), lambda: _shadow_surface(r.size))
        surf.blit(shadow, (r.x - 10, r.y - 6 + int(3 * (1 - self._press))))
        if k > 0.05:
            glow = _remember(("bglow", r.w, r.h), lambda: _glow_surface(r.size))
            glow.set_alpha(int(255 * k))
            surf.blit(glow, glow.get_rect(center=r.center))
        body = gradient_surface((r.w, r.h), top, bot, radius=12)
        surf.blit(body, r)
        pygame.draw.rect(surf, edge, r, 3 if lit else 2, border_radius=12)
        if self.enabled:
            pygame.draw.line(surf, _mix(top, (255, 255, 255), 0.45), (r.x + 12, r.y + 3), (r.right - 12, r.y + 3), 1)
        # brilho diagonal (glint) e onda do clique, limitados ao botão
        old = surf.get_clip()
        surf.set_clip(r.inflate(-4, -4).clip(old))
        if self._glint >= 0 and self.enabled:
            sheen = _sheen()
            x = r.x - _SHEEN_W + self._glint / 1.15 * (r.w + _SHEEN_W * 2)
            surf.blit(sheen, (x, r.centery - sheen.get_height() // 2))
        if self._ripple:
            (rx, ry), rt = self._ripple
            rt += dt * 2.6
            self._ripple = ((rx, ry), rt) if rt < 1 else None
            if self._ripple:
                rad = int(10 + rt * max(r.w, r.h) * 0.8)
                ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (255, 255, 255, int(110 * (1 - rt))), (rad + 2, rad + 2), rad, 4)
                surf.blit(ring, ring.get_rect(center=(rx, ry)))
        surf.set_clip(old)
        cy = r.centery - (9 if self.sub and small_font else 0)
        text(surf, font, self.label, (r.centerx, cy + int(2 * self._press)), txt, "center")
        if self.sub and small_font:
            text(surf, small_font, self.sub, (r.centerx, r.centery + 16), (205, 205, 175) if self.enabled else txt,
                 "center")


def _draw_mc(self, surf, r, font, small_font, lit, dt) -> None:
    """Botão no tema Minecraft: sprite 9-slice + texto com sombra dura (sem gradiente/glint)."""
    if not mcui.button(surf, r, lit, self.enabled):
        return
    if self._ripple:
        self._ripple = None
    cy = r.centery - (9 if self.sub and small_font else 0)
    mcui.label(surf, font, tr(self.label), (r.centerx, cy + int(2 * self._press)), lit, self.enabled)
    if self.sub and small_font:
        mcui.label(surf, small_font, tr(self.sub), (r.centerx, r.centery + 16), False, self.enabled)


Button._draw_mc = _draw_mc


def _glow_surface(size) -> pygame.Surface:
    w, h = size
    s = pygame.Surface((w + 36, h + 36), pygame.SRCALPHA)
    for i, a in enumerate((16, 22, 30, 40)):
        pygame.draw.rect(s, (255, 196, 64, a), (i * 4, i * 4, w + 36 - i * 8, h + 36 - i * 8), border_radius=22 - i * 3)
    return s


class Menu:
    """Lista de botões com foco por teclado (setas/enter), hover do mouse e clique/toque."""

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
        elif inp.moved:                                  # mouse passou por cima: o foco acompanha
            for i, b in enumerate(self.buttons):
                if b.enabled and b.rect.collidepoint(inp.pointer_pos):
                    self.focus = i
                    break
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
                    b.click(pos)
                    return

    def draw(self, surf, font, small_font=None) -> None:
        for i, b in enumerate(self.buttons):
            b.draw(surf, font, i == self.focus, small_font)
