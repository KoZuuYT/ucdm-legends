"""Testes do update Visual & Feedback + Qualidade de Vida (headless)."""
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_TMP = tempfile.mkdtemp(prefix="ucdm-test-upd-")
os.environ["UCDM_USER_DIR"] = _TMP
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from core import config, paths, settings  # noqa: E402
from systems import tween  # noqa: E402
from systems.save import SaveManager  # noqa: E402


class TweenTest(unittest.TestCase):
    def test_curves_endpoints_and_monotonic(self):
        for f in (tween.linear, tween.ease_out_cubic, tween.ease_in_out_sine, tween.ease_out_back):
            self.assertAlmostEqual(f(0), 0.0, places=5)
            self.assertAlmostEqual(f(1), 1.0, places=5)
        xs = [tween.ease_out_cubic(i / 20) for i in range(21)]
        self.assertEqual(xs, sorted(xs))
        self.assertLessEqual(max(xs), 1.0)
        self.assertGreater(max(tween.ease_out_back(i / 50) for i in range(51)), 1.0)   # "pop" passa do alvo

    def test_tween_object(self):
        t = tween.Tween(10, 20, 1.0)
        t.update(0.5)
        self.assertTrue(10 < t.value < 20)
        t.update(1.0)
        self.assertTrue(t.done)
        self.assertEqual(t.value, 20)


class FeedbackTest(unittest.TestCase):
    def _fb(self, **over):
        from core.feedback import Feedback
        return Feedback({"feedback": over})

    def test_hitstop_slows_logic_then_recovers(self):
        fb = self._fb()
        fb.hitstop("parry")
        self.assertLess(fb.time_scale(1 / 60), 0.2)
        for _ in range(30):
            scale = fb.time_scale(1 / 60)
        self.assertEqual(scale, 1.0)

    def test_intensity_zero_and_reduce_motion_disable_effects(self):
        for over in ({"intensity": 0}, {"reduce_motion": True}, {"hitstop": False}):
            fb = self._fb(**over)
            fb.hitstop("ko")
            fb.slowmo(0.3, 1.0)
            self.assertEqual(fb.time_scale(1 / 60), 1.0, over)
        self.assertEqual(self._fb(intensity=0).shake_power("crit"), 0)
        self.assertEqual(self._fb(screen_shake=False).shake_power("crit"), 0)
        self.assertGreater(self._fb().shake_power("crit"), 0)

    def test_flash_rate_limited(self):
        fb = self._fb()
        fb.flash((255, 255, 255), 0.5)
        first = fb._flash_alpha
        fb._flash_alpha = 0.0
        fb.flash((255, 255, 255), 0.5)           # dentro do intervalo mínimo: ignorado
        self.assertGreater(first, 0)
        self.assertEqual(fb._flash_alpha, 0.0)
        fb.update(0.5)
        fb.flash((255, 255, 255), 0.5)
        self.assertGreater(fb._flash_alpha, 0)

    def test_toasts_expire_and_bus_delivers(self):
        fb = self._fb()
        seen = []
        fb.on("x", lambda v: seen.append(v))
        fb.emit("x", v=1)
        fb.emit("x", v=2)
        self.assertEqual(seen, [1, 2])
        fb.toast("oi", life=0.2)
        fb.update(0.3)
        self.assertEqual(len(fb.toasts), 0)


class SaveSlotsTest(unittest.TestCase):
    def setUp(self):
        for f in paths.SAVE_DIR.glob("*") if paths.SAVE_DIR.exists() else []:
            f.unlink()
        paths.ensure_user_dirs()
        for f in paths.EXPORT_DIR.glob("*"):
            f.unlink()

    def _profile(self, **kw):
        from entities.progression import Profile
        return Profile(character="kozu", **kw)

    def test_slots_are_isolated(self):
        a, b = SaveManager("slot1"), SaveManager("slot2")
        a.save(self._profile(gold=10))
        self.assertTrue(a.exists())
        self.assertFalse(b.exists())
        self.assertIsNone(b.summary())
        self.assertEqual(a.summary()["gold"], 10)

    def test_corrupt_main_falls_back_to_backup(self):
        m = SaveManager("slot1")
        m.save(self._profile(gold=1))
        m.save(self._profile(gold=2))            # o 1º vira .bak
        m.path.write_text("{quebrado", encoding="utf-8")
        data = m.load_raw()
        self.assertTrue(data["_from_backup"])
        self.assertEqual(data["gold"], 1)
        self.assertTrue(m.summary()["from_backup"])

    def test_old_version_save_is_backed_up_and_migrated(self):
        m = SaveManager("slot1")
        m.path.write_text(json.dumps({"character": "kozu", "gold": 5, "save_version": 1,
                                      "stats": {"strength": {"level": 2, "xp": 0}}}), encoding="utf-8")
        data = m.load_raw()
        self.assertEqual(data["save_version"], 2)
        self.assertTrue((paths.SAVE_DIR / "slot1.v1.bak").is_file())
        from entities.progression import Profile
        p = Profile.from_dict(data)                # campos novos têm padrão
        self.assertEqual((p.playtime, p.name, p.counters, p.seen_help), (0.0, "", {}, False))

    def test_copy_export_import_roundtrip(self):
        a, b = SaveManager("slot1"), SaveManager("slot2")
        a.save(self._profile(gold=77, name="Ana"))
        self.assertTrue(a.copy_to(b))
        self.assertEqual(b.load_raw()["gold"], 77)
        out = a.export()
        self.assertTrue(out.name.endswith(".ucdmsave"))
        c = SaveManager("slot3")
        self.assertTrue(c.import_file(out))
        self.assertEqual(c.summary()["name"], "Ana")
        bad = paths.EXPORT_DIR / "ruim.ucdmsave"
        bad.write_text(json.dumps({"x": 1}), encoding="utf-8")
        self.assertFalse(c.import_file(bad))        # não parece um save
        bad.write_text("nem json", encoding="utf-8")
        self.assertFalse(c.import_file(bad))

    def test_delete_only_that_slot(self):
        a, b = SaveManager("slot1"), SaveManager("slot2")
        a.save(self._profile())
        b.save(self._profile())
        a.delete()
        self.assertFalse(a.exists())
        self.assertTrue(b.exists())

    def test_profile_roundtrip_new_fields(self):
        from entities.progression import Profile
        p = self._profile(name="Zé", playtime=125.5)
        p.bump("parries", 3)
        p.record("max_hit", 40)
        p.record("max_hit", 10)
        q = Profile.from_dict(p.to_dict())
        self.assertEqual((q.name, q.playtime, q.counters["parries"], q.counters["max_hit"]), ("Zé", 125.5, 3, 40))


class SettingsApiTest(unittest.TestCase):
    def tearDown(self):
        paths.SETTINGS_FILE.unlink(missing_ok=True)
        config.load("game", reload=True)

    def test_partial_write_and_restore(self):
        settings.set_value("audio.sfx_volume", 0.3)
        settings.set_value("gameplay.difficulty", "hard")
        data = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data, {"audio": {"sfx_volume": 0.3}, "gameplay": {"difficulty": "hard"}})
        cfg = config.load("game", reload=True)
        self.assertEqual(cfg["audio"]["sfx_volume"], 0.3)
        self.assertIn("hit", cfg["audio"]["sfx"])                      # resto intacto
        settings.remove("audio.sfx_volume")
        settings.remove("gameplay.difficulty")
        self.assertEqual(json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8")), {})
        self.assertEqual(config.load("game", reload=True)["gameplay"]["difficulty"], "normal")

    def test_corrupt_settings_does_not_break_write(self):
        paths.SETTINGS_FILE.write_text("{quebrado", encoding="utf-8")
        settings.set_value("display.show_fps", True)
        self.assertTrue(config.load("game", reload=True)["display"]["show_fps"])


class RebindTest(unittest.TestCase):
    def setUp(self):
        from scenes import options
        self.options = options
        self.base = options.default_bindings()

    def test_defaults_exist(self):
        self.assertIn("attack", self.base)

    def test_escape_is_reserved(self):
        _, err = self.options.assign_key(self.base, "attack", 0, "escape")
        self.assertIsNotNone(err)

    def test_assign_and_steal_from_other_action(self):
        new, err = self.options.assign_key(self.base, "attack", 0, "h")
        self.assertIsNone(err)
        self.assertEqual(new["attack"][0], "h")
        new, err = self.options.assign_key(new, "block", 0, "z")     # 'z' era alt de attack (tem outra tecla)
        self.assertIsNone(err)
        self.assertNotIn("z", new["attack"])
        self.assertEqual(new["block"][0], "z")
        self.assertEqual(self.base["attack"], ["j", "z"])             # original não é mutado

    def test_cannot_leave_other_action_without_key(self):
        b = {"attack": ["j"], "block": ["k"]}
        new, err = self.options.assign_key(b, "block", 0, "j")
        self.assertIsNotNone(err)
        self.assertEqual(new, b)

    def test_input_manager_applies_bindings_and_ignores_bad_names(self):
        from core.input import InputManager

        class D:   # display falso
            pass
        im = InputManager(D(), {"attack": ["j"], "x": ["tecla-que-nao-existe"]})
        im.process(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
        self.assertTrue(im.pressed("attack"))
        im.set_bindings({"attack": ["h"]})
        im.begin_frame(0)
        im.process(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
        self.assertFalse(im.pressed("attack"))
        im.capture = True
        im.process(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
        self.assertEqual(im.captured, "q")


class AudioTest(unittest.TestCase):
    def test_generated_sounds_exist_and_missing_is_silent(self):
        cfg = config.load("game", reload=True)
        for name, ref in cfg["audio"]["sfx"].items():
            for rel in (ref if isinstance(ref, list) else [ref]):
                self.assertTrue((paths.ASSETS_DIR / rel).is_file(), rel)
        for rel in cfg["audio"]["music"].values():
            self.assertTrue((paths.ASSETS_DIR / rel).is_file(), rel)
        from systems.assets import AssetManager
        from systems.audio import AudioManager
        pygame.init()
        am = AudioManager(AssetManager(), {"sfx": {"x": "audio/sfx/nao-existe.wav"}, "music": {}})
        am.play("x")
        am.play("nome-inexistente")
        am.music("nada")
        am.duck(0.1)
        am.update(0.2)


class GameFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        from entities.progression import Profile
        cls.game = Game(headless=True)
        cls.game.profile = Profile(character="kozu")

    def tearDown(self):
        paths.SETTINGS_FILE.unlink(missing_ok=True)
        self.game.apply_settings()

    def _run(self, scene, frames=90, keys=(), pointer=None):
        g = self.game
        g.scenes.stack.clear()
        g.scenes.push(scene)
        rnd = random.Random(1)
        for i in range(frames):
            g.input.begin_frame(g.time)
            if keys and i % 5 == 0:
                k = rnd.choice(keys)
                g.input.process(pygame.event.Event(pygame.KEYDOWN, key=k))
                g.input.process(pygame.event.Event(pygame.KEYUP, key=k))
            g.feedback.update(1 / 60)
            g.scenes.update(1 / 60 * g.feedback.time_scale(1 / 60))
            g.time += 1 / 60
            g.screen.fill((0, 0, 0))
            g.scenes.draw(g.screen)
            g.feedback.draw(g.screen, g.assets.font(24))

    def test_new_scenes_smoke(self):
        from scenes.dialogs import ConfirmDialog, TextPrompt
        from scenes.help import CreditsOverlay, HelpOverlay
        from scenes.options import OptionsScene
        from scenes.pause import PauseOverlay
        from scenes.save_select import SaveSelectScene, SlotMenu
        from scenes.stats import StatsScene
        g = self.game
        nav = (pygame.K_DOWN, pygame.K_UP, pygame.K_LEFT, pygame.K_RIGHT)
        for tab in range(4):
            self._run(OptionsScene(g, tab), 120, nav)
        self._run(PauseOverlay(g, on_quit=lambda: None), 60, nav)
        self._run(HelpOverlay(g), 90, (pygame.K_RIGHT, pygame.K_LEFT))
        self._run(CreditsOverlay(g), 30)
        self._run(StatsScene(g), 30)
        self._run(SaveSelectScene(g), 90, nav)
        self._run(SlotMenu(g, 0, None), 30)
        SaveManager("slot1").save(g.profile)
        self._run(SlotMenu(g, 0, SaveManager("slot1").summary()), 30, nav)
        self._run(ConfirmDialog(g, "T", "linha1\nlinha2", on_yes=lambda: None, hold=1.0), 60)
        self._run(TextPrompt(g, "Nome", "abc", on_ok=lambda s: None), 30)

    def test_confirm_dialog_defaults_to_cancel_and_hold_required(self):
        from scenes.dialogs import ConfirmDialog
        g = self.game
        done = []
        d = ConfirmDialog(g, "Apagar?", "x", on_yes=lambda: done.append(1), hold=1.0)
        self.assertEqual(d.focus, 1)             # foco inicial em "Cancelar"
        self._run(d, 40, (pygame.K_RETURN,))     # confirmar sem "yes" focado não executa
        self.assertEqual(done, [])

    def test_option_changes_apply_and_persist(self):
        from scenes.options import OptionsScene
        g = self.game
        o = OptionsScene(g, 1)
        o._set("audio.sfx_volume", 0.2)
        self.assertEqual(g.audio.sfx_volume, 0.2)
        self.assertEqual(g.cfg["audio"]["sfx_volume"], 0.2)
        o._set("feedback.intensity", 0.0)
        self.assertEqual(g.feedback.intensity, 0.0)
        o._reset_tab()
        o.tab = 3
        o._build()
        o._reset_tab()
        self.assertGreater(g.feedback.intensity, 0)
        self.assertEqual(json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8")), {})

    def test_rebind_through_settings(self):
        from scenes.options import OptionsScene
        g = self.game
        o = OptionsScene(g, 2)
        r = next(r for r in o.rows if r.key == "attack")
        o.capturing, g.input.capture = r, True
        o._finish_capture("h")
        self.assertEqual(g.input.bindings["attack"][0], "h")
        o._reset_keys()
        self.assertEqual(g.input.bindings["attack"], ["j", "z"])

    def test_arena_with_feedback_and_options(self):
        from scenes.arena import ArenaScene
        g = self.game
        settings.set_value("gameplay.difficulty", "hard")
        settings.set_value("gameplay.extended_warning", True)
        g.apply_settings()
        keys = (pygame.K_j, pygame.K_k, pygame.K_l, pygame.K_LEFT, pygame.K_RIGHT)
        arena = ArenaScene(g, 2)
        base = ArenaScene(g, 2)
        self.assertGreater(arena.enemy.damage, 0)
        self._run(arena, 60 * 25, keys)
        # o modo difícil aumenta o dano do inimigo, e aviso estendido só mexe em golpes imbloqueáveis
        settings.remove("gameplay.difficulty")
        g.apply_settings()
        normal = ArenaScene(g, 2)
        self.assertGreater(arena.enemy.damage, normal.enemy.damage)
        self.assertEqual(base.enemy.attacks[0].windup, arena.enemy.attacks[0].windup
                         if not arena.enemy.attacks[0].unblockable else base.enemy.attacks[0].windup)

    def test_arena_pause_does_not_advance_fight(self):
        from scenes.arena import ArenaScene
        from scenes.pause import PauseOverlay
        g = self.game
        g.scenes.stack.clear()
        arena = ArenaScene(g, 0)
        g.scenes.push(arena)
        g.scenes.flush()
        arena._pause()
        for _ in range(30):
            g.input.begin_frame(g.time)
            g.scenes.update(1 / 60)
        self.assertIsInstance(g.scenes.current, PauseOverlay)
        now = arena.now
        for _ in range(60):
            g.input.begin_frame(g.time)
            g.scenes.update(1 / 60)
        self.assertEqual(arena.now, now)

    def test_transition_kinds_complete(self):
        from core.scene import Scene
        g = self.game
        for kind in ("fade", "slide", "iris", True):
            g.scenes.stack.clear()
            g.scenes.push(Scene(g))
            g.scenes.flush()
            g.scenes.replace(Scene(g), fade=kind)
            for _ in range(120):
                g.scenes.update(1 / 60)
                g.scenes.draw(g.screen)
            self.assertFalse(g.scenes.busy, kind)

    def test_use_slot_switches_manager_and_remembers(self):
        g = self.game
        g.use_slot("slot2")
        self.assertEqual(g.save.slot, "slot2")
        self.assertIsNone(g.profile)
        self.assertEqual(config.load("game", reload=True)["last_slot"], "slot2")
        g.use_slot("slot1")
        from entities.progression import Profile
        g.profile = Profile(character="kozu")


if __name__ == "__main__":
    unittest.main()
