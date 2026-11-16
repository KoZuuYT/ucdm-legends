"""Áudio com degradação graciosa: sem placa de som ou sem arquivo = silêncio, nunca crash.

Sons são referenciados por nome lógico em assets/data/game.json -> audio.sfx. Cada nome pode apontar
para um arquivo ou para uma LISTA de variações (sorteia uma por vez, evitando repetição seca).
Trocar um efeito sonoro é só trocar o arquivo/JSON."""
import random
import time

import pygame

_MIN_GAP = 0.035          # s: mesmo som repetido antes disso é ignorado (evita estouro em combos)
_EXTS = (".wav", ".ogg")


class AudioManager:
    def __init__(self, assets, cfg: dict) -> None:
        self.assets = assets
        self.enabled = False
        self.sfx_map: dict = {}
        self.music_map: dict[str, str] = {}
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.configure(cfg)
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self.enabled = True
        except pygame.error as e:
            print(f"[audio] desativado: {e}")
        self.recent: list[tuple[str, float]] = []        # efeitos tocados há pouco (legendas)
        self._current_music: str | None = None
        self._last: dict[str, float] = {}
        self._duck = 0.0
        self.apply_volumes()

    def configure(self, cfg: dict) -> None:
        self.sfx_map = cfg.get("sfx", {})
        self.music_map = cfg.get("music", {})
        self.sfx_volume = float(cfg.get("sfx_volume", 0.8))
        self.music_volume = float(cfg.get("music_volume", 0.5))

    def apply_volumes(self) -> None:
        if self.enabled:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, self.music_volume * (1 - 0.35 * min(1.0, self._duck)))))

    def _pick(self, name: str) -> str | None:
        ref = self.sfx_map.get(name)
        if isinstance(ref, (list, tuple)):
            return random.choice(ref) if ref else None
        if ref:
            return ref
        for ext in _EXTS:
            rel = f"audio/sfx/{name}{ext}"
            if self.assets.resolve(rel):
                return rel
        return None

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        if now - self._last.get(name, -1.0) < _MIN_GAP:
            return
        self._last[name] = now
        self.recent.append((name, now))
        del self.recent[:-8]
        rel = self._pick(name)
        snd = self.assets.sound(rel) if rel else None
        if snd:
            snd.set_volume(max(0.0, min(1.0, self.sfx_volume * volume * random.uniform(0.92, 1.0))))
            snd.play()

    def duck(self, seconds: float = 0.5) -> None:
        """Abaixa a música por instantes (KO, parry)."""
        self._duck = max(self._duck, seconds)
        self.apply_volumes()

    def update(self, dt: float) -> None:
        if self._duck > 0:
            self._duck = max(0.0, self._duck - dt)
            self.apply_volumes()

    def music(self, name: str | None, fade_ms: int = 600) -> None:
        if not self.enabled or name == self._current_music:
            return
        self._current_music = name
        pygame.mixer.music.fadeout(fade_ms)
        if not name:
            return
        ref = self.music_map.get(name)
        path = self.assets.resolve(ref) if ref else None
        if path is None:
            for ext in _EXTS:
                path = self.assets.resolve(f"audio/music/{name}{ext}")
                if path:
                    break
        if path:
            try:
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1, fade_ms=fade_ms)
            except pygame.error as e:
                print(f"[audio] música {name}: {e}")
