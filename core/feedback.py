"""Camada central de feedback: hitstop, câmera lenta, flash de tela, toasts e indicador de save.

As cenas só pedem ("houve um parry"); a intensidade e os liga/desliga (acessibilidade) vivem aqui,
lidos de assets/data/feedback.json + settings.json -> "feedback". Nada disto altera a lógica do jogo:
o hitstop só reduz o dt entregue às cenas, e tudo com intensidade 0 vira no-op.
"""
from collections import deque

import pygame

from core import config

_SCALE_MIN = 0.02


class Toast:
    __slots__ = ("msg", "color", "life", "total")

    def __init__(self, msg: str, color, life: float) -> None:
        self.msg, self.color, self.life, self.total = msg, color, life, life


class Feedback:
    def __init__(self, game_cfg: dict) -> None:
        self.cfg: dict = {}
        self.reload(game_cfg)
        self._hitstop = 0.0
        self._slowmo = 0.0
        self._slowmo_scale = 1.0
        self._flash_color = (255, 255, 255)
        self._flash_alpha = 0.0
        self._flash_cool = 0.0
        self._overlay: pygame.Surface | None = None
        self.toasts: deque[Toast] = deque(maxlen=4)
        self.saved_timer = 0.0
        self.events: dict[str, list] = {}

    def reload(self, game_cfg: dict) -> None:
        self.cfg = config.deep_merge(config.load("feedback"), game_cfg.get("feedback", {}))

    # --- configuração ------------------------------------------------------------------
    @property
    def intensity(self) -> float:
        return max(0.0, float(self.cfg.get("intensity", 1.0)))

    @property
    def reduce_motion(self) -> bool:
        return bool(self.cfg.get("reduce_motion", False))

    def shake_power(self, kind: str) -> float:
        if not self.cfg.get("screen_shake", True) or self.reduce_motion:
            return 0.0
        return float(self.cfg.get("shake", {}).get(kind, 0)) * self.intensity

    # --- barramento simples -------------------------------------------------------------
    def on(self, event: str, fn) -> None:
        self.events.setdefault(event, []).append(fn)

    def emit(self, event: str, **kw) -> None:
        for fn in self.events.get(event, ()):
            fn(**kw)

    # --- efeitos de tempo ---------------------------------------------------------------
    def hitstop(self, kind: str) -> None:
        if not self.cfg.get("hitstop", True) or self.intensity <= 0 or self.reduce_motion:
            return
        self._hitstop = max(self._hitstop, float(self.cfg.get("hitstop_time", {}).get(kind, 0.04)) * self.intensity)

    def slowmo(self, scale: float, seconds: float) -> None:
        if not self.cfg.get("hitstop", True) or self.intensity <= 0 or self.reduce_motion:
            return
        self._slowmo, self._slowmo_scale = max(self._slowmo, seconds), scale

    def ko(self) -> None:
        k = self.cfg.get("ko_slowmo", {})
        self.hitstop("ko")
        self.slowmo(float(k.get("scale", 0.3)), float(k.get("time", 0.7)))

    def time_scale(self, real_dt: float) -> float:
        """Fator aplicado ao dt da lógica neste frame (1.0 = normal)."""
        scale = 1.0
        if self._hitstop > 0:
            self._hitstop -= real_dt
            scale = float(self.cfg.get("hitstop_scale", 0.06))
        elif self._slowmo > 0:
            self._slowmo -= real_dt
            scale = self._slowmo_scale
        return max(_SCALE_MIN, scale)

    # --- flash de tela ------------------------------------------------------------------
    def flash(self, color=(255, 255, 255), alpha: float = 0.5) -> None:
        """Flash curto; respeita intensidade, opção de flash e o limite de flashes por segundo."""
        if not self.cfg.get("flash", True) or self.reduce_motion or self.intensity <= 0 or self._flash_cool > 0:
            return
        hz = max(1.0, float(self.cfg.get("flash_max_hz", 3)))
        self._flash_cool = 1.0 / hz
        self._flash_color = color
        self._flash_alpha = min(0.8, alpha * self.intensity)

    # --- toasts / save ------------------------------------------------------------------
    def toast(self, msg: str, color=(240, 240, 240), life: float = 2.4) -> None:
        self.toasts.append(Toast(msg, color, life))

    def saved(self) -> None:
        self.saved_timer = 1.6

    # --- ciclo (tempo real, independente de hitstop) --------------------------------------
    def update(self, real_dt: float) -> None:
        self._flash_alpha = max(0.0, self._flash_alpha - real_dt * 3.2)
        self._flash_cool = max(0.0, self._flash_cool - real_dt)
        self.saved_timer = max(0.0, self.saved_timer - real_dt)
        for t in self.toasts:
            t.life -= real_dt
        while self.toasts and self.toasts[0].life <= 0:
            self.toasts.popleft()

    def draw(self, surf: pygame.Surface, font) -> None:
        w, h = surf.get_size()
        if self._flash_alpha > 0.01:
            if self._overlay is None or self._overlay.get_size() != (w, h):
                self._overlay = pygame.Surface((w, h))
            self._overlay.fill(self._flash_color)
            self._overlay.set_alpha(int(255 * self._flash_alpha))
            surf.blit(self._overlay, (0, 0))
        y = h - 24
        for t in reversed(self.toasts):
            k = min(1.0, t.life / 0.35, (t.total - t.life) / 0.2 + 0.001)
            img = font.render(t.msg, True, t.color)
            box = img.get_rect().inflate(36, 18)
            box.midbottom = (w // 2, y + int((1 - k) * 18))
            s = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(s, (18, 20, 30, int(215 * k)), s.get_rect(), border_radius=12)
            pygame.draw.rect(s, (*t.color, int(160 * k)), s.get_rect(), 2, border_radius=12)
            img.set_alpha(int(255 * k))
            s.blit(img, img.get_rect(center=(box.w // 2, box.h // 2)))
            surf.blit(s, box)
            y -= box.h + 8
        if self.saved_timer > 0:
            a = int(255 * min(1.0, self.saved_timer / 0.5))
            img = font.render("Salvo", True, (120, 230, 140))
            img.set_alpha(a)
            r = img.get_rect(topright=(w - 14, 10))
            surf.blit(img, r)
            tick = pygame.Surface((22, 18), pygame.SRCALPHA)   # o "✓" é desenhado (a fonte padrão não tem o glifo)
            pygame.draw.lines(tick, (120, 230, 140, a), False, [(2, 10), (8, 16), (20, 2)], 3)
            surf.blit(tick, tick.get_rect(midright=(r.left - 6, r.centery)))
