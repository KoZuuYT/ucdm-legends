"""Core loop: timestep fixo para lógica (determinística, independente de FPS)
e renderização desacoplada. Também é o "service locator" dos sistemas."""
import os
import time

import pygame

from core import config, paths, settings, ui
from core.display import Display
from core.events import EventBus
from core.feedback import Feedback
from core.input import InputManager
from core.scene import Scene, SceneManager


class Game:
    def __init__(self, *, headless: bool = False) -> None:
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        paths.ensure_user_dirs()
        pygame.init()
        self.cfg = config.load("game")
        disp = self.cfg["display"]
        self.display = Display(disp["width"], disp["height"], self.cfg["title"],
                               fullscreen=disp.get("fullscreen", False),
                               vsync=disp.get("vsync", True), headless=headless)
        self.screen = self.display.surface
        self.events = EventBus()
        self.feedback = Feedback(self.cfg)
        self.input = InputManager(self.display, self.cfg["input"])
        self.scenes = SceneManager()

        # Sistemas importados aqui para manter o core independente deles.
        from systems.assets import AssetManager
        from systems.audio import AudioManager
        from systems.save import SaveManager
        self.assets = AssetManager()
        self.audio = AudioManager(self.assets, self.cfg.get("audio", {}))
        self._SaveManager = SaveManager
        self.slot = self.cfg.get("last_slot", "slot1")
        self.save = SaveManager(self.slot, on_saved=self.feedback.saved)
        self.profile = None  # entities.progression.Profile, definido no menu
        ui.sound_hook = self.audio.play   # botões tocam hover/click sem conhecer o jogo

        self.tick_rate = disp.get("tick_rate", 60)
        self.fps_cap = disp.get("fps_cap", 144) or 0   # 0 = sem limite
        self.show_debug = bool(disp.get("show_fps", False))
        self.running = False
        self.time = 0.0
        self.fps = 0.0

    # --- slots e preferências ---------------------------------------------------------
    def use_slot(self, slot: str) -> None:
        """Troca o slot de save ativo (grava o perfil atual antes, se houver)."""
        if self.profile is not None:
            self.save.save(self.profile)
        self.slot = slot
        self.profile = None
        self.save = self._SaveManager(slot, on_saved=self.feedback.saved)
        settings.set_value("last_slot", slot)

    def apply_settings(self) -> None:
        """Relê settings.json e aplica o que dá para mudar sem reiniciar."""
        self.cfg = config.load("game", reload=True)
        disp = self.cfg["display"]
        self.fps_cap = disp.get("fps_cap", 144) or 0
        self.show_debug = bool(disp.get("show_fps", False))
        if not self.headless and bool(disp.get("fullscreen", False)) != self.display.fullscreen:
            self.display.toggle_fullscreen()
        self.audio.configure(self.cfg.get("audio", {}))
        self.audio.apply_volumes()
        self.feedback.reload(self.cfg)
        self.input.set_bindings(self.cfg["input"])

    def run(self, first_scene: Scene, *, max_frames: int | None = None) -> None:
        self.scenes.push(first_scene)
        self.scenes.flush()   # a 1ª cena entra antes do 1º quadro (senão a pilha parece vazia)
        clock = pygame.time.Clock()
        step = 1.0 / self.tick_rate
        acc = 0.0
        last = time.perf_counter()
        frames = 0
        self.running = True
        while self.running:
            now = time.perf_counter()
            # clamp evita "espiral da morte" após travadas (ex.: arrastar janela)
            frame_dt = step if self.headless else min(now - last, 0.25)
            last = now
            acc += frame_dt

            self.input.begin_frame(self.time)
            for ev in pygame.event.get():
                self.input.process(ev)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F3:
                    self.show_debug = not self.show_debug
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    self.display.toggle_fullscreen()
                elif ev.type == pygame.WINDOWFOCUSLOST and self.cfg.get("gameplay", {}).get("auto_pause", True):
                    if self.scenes.current:
                        self.scenes.current.on_focus_lost()
            if self.input.quit_requested:
                self.quit()

            # Lógica a 60 Hz fixos. Ações "pressed" valem só no 1º passo do frame.
            self.feedback.update(frame_dt)
            self.audio.update(frame_dt)
            if self.profile is not None:
                self.profile.playtime += frame_dt
            scale = self.feedback.time_scale(frame_dt)   # hitstop / câmera lenta (só visual)
            first = True
            while acc >= step:
                if not first:
                    self.input.consume_step()
                self.scenes.update(step * scale)
                self.time += step
                acc -= step
                first = False

            self.screen.fill((0, 0, 0))
            self.scenes.draw(self.screen)
            self.feedback.draw(self.screen, self.assets.font(24))
            if self.show_debug:
                self._draw_debug()
            self.display.present()
            self.assets.end_frame()

            clock.tick(0 if self.headless else self.fps_cap)
            self.fps = clock.get_fps()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                self.running = False
            if not self.scenes.stack and not self.scenes.busy:
                self.running = False
        self.shutdown()

    def _draw_debug(self) -> None:
        font = self.assets.font(16)
        scene = self.scenes.current
        extra = getattr(scene, "debug_info", lambda: "")()
        lines = [f"FPS {self.fps:5.1f}", f"Cena {type(scene).__name__}",
                 f"Texturas {self.assets.stats()}", extra]
        for i, line in enumerate(l for l in lines if l):
            t = font.render(line, True, (255, 255, 0), (0, 0, 0))
            self.screen.blit(t, (8, 8 + i * 18))

    def quit(self) -> None:
        self.running = False

    def shutdown(self) -> None:
        if self.profile is not None:
            self.save.save(self.profile)
        pygame.quit()
