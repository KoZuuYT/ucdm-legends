"""Áudio com degradação graciosa: sem placa de som ou sem arquivo = silêncio, nunca crash.

Sons são referenciados por nome lógico em assets/data/game.json -> audio.sfx,
então trocar um efeito sonoro é só trocar o arquivo/JSON."""
import pygame



class AudioManager:
    def __init__(self, assets, cfg: dict) -> None:
        self.assets = assets
        self.sfx_map: dict[str, str] = cfg.get("sfx", {})
        self.music_map: dict[str, str] = cfg.get("music", {})
        self.sfx_volume = cfg.get("sfx_volume", 0.8)
        self.music_volume = cfg.get("music_volume", 0.5)
        self.enabled = False
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self.enabled = True
        except pygame.error as e:
            print(f"[audio] desativado: {e}")
        self._current_music: str | None = None

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled:
            return
        snd = self.assets.sound(self.sfx_map.get(name, f"audio/sfx/{name}.ogg"))
        if snd:
            snd.set_volume(self.sfx_volume * volume)
            snd.play()

    def music(self, name: str | None, fade_ms: int = 600) -> None:
        if not self.enabled or name == self._current_music:
            return
        self._current_music = name
        pygame.mixer.music.fadeout(fade_ms)
        if not name:
            return
        path = self.assets.resolve(self.music_map.get(name, f"audio/music/{name}.ogg"))
        if path:
            try:
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1, fade_ms=fade_ms)
            except pygame.error as e:
                print(f"[audio] música {name}: {e}")
