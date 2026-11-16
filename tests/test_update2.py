"""Testes do conteúdo complementar: idiomas, acessibilidade, parallax/ambiente, miniaturas, gamepad,
integridade, atualização em segundo plano, novidades e opções novas (headless)."""
import getpass
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("UCDM_USER_DIR", tempfile.mkdtemp(prefix="ucdm-test-upd2-"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from core import config, i18n, paths, settings, ui  # noqa: E402


class I18nTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("pt-BR")

    def test_portuguese_is_identity_and_unknown_language_falls_back(self):
        self.assertEqual(i18n.tr("Opções"), "Opções")
        self.assertEqual(i18n.set_language("xx-inexistente"), "pt-BR")
        self.assertEqual(i18n.tr("Opções"), "Opções")

    def test_english_exact_pattern_and_fallback(self):
        self.assertEqual(i18n.set_language("en"), "en")
        self.assertEqual(i18n.tr("Opções"), "Options")
        self.assertEqual(i18n.tr("Arma nv 3"), "Weapon lv 3")             # padrão específico vence o genérico
        self.assertEqual(i18n.tr("Força nv 4"), "Strength lv 4")          # e traduz o trecho variável
        self.assertEqual(i18n.tr("<  Fácil  >"), "<  Easy  >")
        self.assertEqual(i18n.tr("+12 ouro"), "+12 gold")
        self.assertEqual(i18n.tr("Texto que ninguém traduziu"), "Texto que ninguém traduziu")
        self.assertEqual(i18n.tr(42), 42)

    def test_every_english_entry_is_well_formed(self):
        data = json.loads((paths.DATA_DIR / "lang" / "en.json").read_text(encoding="utf-8"))["strings"]
        for k, v in data.items():
            self.assertEqual(k.count("{}"), v.count("{}"), k)             # mesmos placeholders na ida e na volta
        self.assertIn(("en", "English"), i18n.available())

    def test_ui_text_translates(self):
        pygame.init()
        i18n.set_language("en")
        surf = pygame.Surface((300, 60))
        font = pygame.font.Font(None, 30)
        r_en = ui.text(surf, font, "Opções", (0, 0))
        i18n.set_language("pt-BR")
        r_pt = ui.text(surf, font, "Opções", (0, 0))
        self.assertNotEqual(r_en.width, r_pt.width)                        # "Options" ≠ "Opções" em largura


class AccessibilityTest(unittest.TestCase):
    def tearDown(self):
        ui.apply_accessibility(colorblind_mode=False, high_contrast_mode=False)

    def test_colorblind_and_contrast(self):
        base_red, base_green = ui.RED, ui.GREEN
        ui.apply_accessibility(colorblind_mode=True, high_contrast_mode=True)
        self.assertNotEqual(ui.RED, base_red)
        self.assertNotEqual(ui.GREEN, base_green)
        self.assertTrue(ui.high_contrast)
        self.assertEqual(ui.stat_color("strength", (1, 2, 3)), (213, 94, 0))
        ui.apply_accessibility(colorblind_mode=False, high_contrast_mode=False)
        self.assertEqual((ui.RED, ui.GREEN), (base_red, base_green))
        self.assertEqual(ui.stat_color("strength", (1, 2, 3)), (1, 2, 3))

    def test_icons_render_for_all_stats(self):
        from core import icons
        pygame.init()
        for stat in ("strength", "defense", "agility", "focus", "outro"):
            img = icons.stat_icon(stat, 24, (200, 100, 50))
            self.assertEqual(img.get_size(), (24, 24))
            self.assertGreater(pygame.mask.from_surface(img).count(), 20, stat)   # desenhou algo
        self.assertIs(icons.stat_icon("focus", 24, (200, 100, 50)), icons.stat_icon("focus", 24, (200, 100, 50)))

    def test_font_scale(self):
        from systems.assets import AssetManager
        pygame.init()
        a = AssetManager()
        h1 = a.font(30).get_height()
        a.set_font_scale(1.12)
        self.assertGreater(a.font(30).get_height(), h1)
        a.set_font_scale(5)
        self.assertLessEqual(a.font_scale, 1.4)


class ScenerySystemsTest(unittest.TestCase):
    def test_parallax_and_ambient_draw_every_theme(self):
        from systems import backdrop
        from systems.ambient import Ambient
        pygame.init()
        surf = pygame.Surface((640, 360))
        for theme in backdrop.THEMES:
            backdrop.draw(surf, theme, 300, None, scroll=50, t=3.0)
            backdrop.draw(surf, theme, 300, None, parallax=False)
            Ambient(theme, (640, 360)).draw(surf, 2.5, 100)

    def test_parallax_layers_move_at_different_speeds(self):
        from systems import backdrop
        pygame.init()
        a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
        backdrop.draw(a, "meadow", 300, None, scroll=0, t=0)
        backdrop.draw(b, "meadow", 300, None, scroll=200, t=0)
        self.assertNotEqual(pygame.image.tobytes(a, "RGB"), pygame.image.tobytes(b, "RGB"))

    def test_thumbnails_exist_for_every_character(self):
        from entities import roster
        from systems.assets import AssetManager
        a = AssetManager()
        for c in roster.characters():
            self.assertTrue(a.thumb_path(c).startswith("sprites/thumbs/"), c["id"])
        self.assertEqual(a.thumb_path({"id": "nao-existe", "sprite": "sprites/characters/kozu.png"}),
                         "sprites/characters/kozu.png")


class GamepadTest(unittest.TestCase):
    def setUp(self):
        from core.input import InputManager

        class D:
            pass
        self.im = InputManager(D(), {"attack": ["j"]})
        self.im.begin_frame(0)

    def ev(self, t, **kw):
        self.im.process(pygame.event.Event(t, **kw))

    def test_buttons_hat_and_stick_map_to_actions(self):
        self.ev(pygame.JOYBUTTONDOWN, button=0)
        self.assertTrue(self.im.pressed("confirm") and self.im.pressed("attack"))
        self.ev(pygame.JOYBUTTONUP, button=0)
        self.assertFalse(self.im.held("attack"))
        self.ev(pygame.JOYHATMOTION, value=(-1, 0))
        self.assertTrue(self.im.held("left"))
        self.ev(pygame.JOYHATMOTION, value=(0, 0))
        self.assertFalse(self.im.held("left"))
        self.ev(pygame.JOYAXISMOTION, axis=0, value=0.9)
        self.assertTrue(self.im.held("right"))
        self.ev(pygame.JOYAXISMOTION, axis=0, value=0.1)                   # dentro da zona morta
        self.assertFalse(self.im.held("right"))
        self.ev(pygame.JOYBUTTONDOWN, button=7)
        self.assertTrue(self.im.pressed("back"))

    def test_hat_and_stick_do_not_release_each_other(self):
        self.ev(pygame.JOYHATMOTION, value=(1, 0))
        self.ev(pygame.JOYAXISMOTION, axis=0, value=0.9)
        self.ev(pygame.JOYAXISMOTION, axis=0, value=0.0)
        self.assertTrue(self.im.held("right"))                              # o hat ainda segura

    def test_device_removed_releases_directions(self):
        self.ev(pygame.JOYHATMOTION, value=(0, 1))
        self.ev(pygame.JOYDEVICEREMOVED, instance_id=3)
        self.assertFalse(self.im.held("up"))
        self.ev(pygame.JOYDEVICEADDED, device_index=99)                    # índice inexistente não derruba


class IntegrityTest(unittest.TestCase):
    def test_manifest_has_hashes_and_verify_detects_changes(self):
        from network import integrity
        from network import release_tools as rt
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.txt").write_text("um")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("dois")
            rt.write_manifest(root, "9.9.9")
            man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(man["hashes"]), {"a.txt", "sub/b.txt"})
            self.assertEqual(integrity.verify(root)["state"], "ok")
            (root / "a.txt").write_text("alterado")
            (root / "sub" / "b.txt").unlink()
            (root / "usuario.txt").write_text("fora do manifest")          # arquivo extra é ignorado
            r = integrity.verify(root)
            self.assertEqual((r["state"], r["modified"], r["missing"]), ("problems", ["a.txt"], ["sub/b.txt"]))

    def test_old_manifest_checks_existence_only_and_missing_manifest(self):
        from network import integrity
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(integrity.verify(root)["state"], "nomanifest")
            (root / "manifest.json").write_text(json.dumps({"version": "0.1.0", "files": ["x.txt"]}))
            self.assertEqual(integrity.verify(root)["missing"], ["x.txt"])
            (root / "x.txt").write_text("qualquer coisa")
            r = integrity.verify(root)
            self.assertEqual((r["state"], r["hashed"]), ("ok", False))


class GameExtrasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        from entities.progression import Profile
        cls.game = Game(headless=True)
        cls.game.profile = Profile()

    def setUp(self):
        paths.SETTINGS_FILE.unlink(missing_ok=True)
        self.game.apply_settings()

    def tearDown(self):
        paths.SETTINGS_FILE.unlink(missing_ok=True)
        self.game.apply_settings()

    def _run(self, scene, frames=60):
        g = self.game
        g.scenes.stack.clear()
        g.scenes.push(scene)
        for _ in range(frames):
            g.input.begin_frame(g.time)
            g.feedback.update(1 / 60)
            g.scenes.update(1 / 60)
            g.time += 1 / 60
            g.screen.fill((0, 0, 0))
            g.scenes.draw(g.screen)
            g.feedback.draw(g.screen, g.assets.font(24))

    def test_sysinfo_has_no_personal_data(self):
        from core import sysinfo
        text = sysinfo.collect(self.game)
        self.assertIn("UCDM Legends", text)
        self.assertNotIn(getpass.getuser(), text)
        self.assertNotIn(str(Path.home()), text)
        path = sysinfo.save_to_file(text)
        self.assertTrue(path.is_file())

    def test_settings_drive_language_contrast_and_text_size(self):
        g = self.game
        settings.set_value("language", "en")
        settings.set_value("accessibility.high_contrast", True)
        settings.set_value("accessibility.text_scale", 1.12)
        g.apply_settings()
        self.assertEqual(i18n.language(), "en")
        self.assertTrue(ui.high_contrast)
        self.assertEqual(g.assets.font_scale, 1.12)
        from scenes.hub import HubScene
        from scenes.menu import MenuScene
        self._run(MenuScene(g), 20)
        self._run(HubScene(g), 20)
        settings.remove("language")
        settings.remove("accessibility")
        g.apply_settings()
        self.assertEqual(i18n.language(), "pt-BR")
        self.assertFalse(ui.high_contrast)

    def test_low_performance_mode_and_zoom(self):
        from scenes.arena import ArenaScene
        g = self.game
        settings.set_value("performance.low_mode", True)
        g.apply_settings()
        arena = ArenaScene(g, 0)
        self.assertTrue(g.low_perf)
        self.assertFalse(arena.player.ghosts_on)
        self._run(arena, 30)
        settings.remove("performance")
        g.apply_settings()
        arena = ArenaScene(g, 0)
        arena.result, arena.over = "win", 0.7
        self.assertGreater(arena._zoom(), 1.01)                            # zoom do KO
        self._run(arena, 5)
        settings.set_value("feedback.reduce_motion", True)
        g.apply_settings()
        self.assertEqual(arena._zoom(), 1.0)

    def test_hub_train_again_button(self):
        from scenes.hub import HubScene
        g = self.game
        g.profile.last_training = ""
        hub = HubScene(g)
        again = next(b for b in hub.menu.buttons if b.label == "Treinar de novo")
        self.assertFalse(again.enabled)
        g.profile.last_training = "slash"
        hub = HubScene(g)
        again = next(b for b in hub.menu.buttons if b.label == "Treinar de novo")
        self.assertTrue(again.enabled)
        self.assertEqual(again.sub, "Treino de Golpe")
        g.profile.last_training = ""

    def test_news_shown_once_after_update(self):
        from scenes.menu import MenuScene
        from scenes.news import NewsOverlay, split_sentences, wrap_text
        g = self.game
        self.assertEqual(split_sentences("Um. Dois. Três."), ["Um.", "Dois.", "Três."])
        font = pygame.font.Font(None, 24)
        for line in wrap_text(font, "palavra " * 40, 300):
            self.assertLessEqual(font.size(line)[0], 300)
        g.cfg.pop("last_seen_version", None)
        g.scenes.stack.clear()
        g.scenes.push(MenuScene(g))
        g.scenes.flush()
        g.scenes.flush()
        self.assertIsInstance(g.scenes.current, NewsOverlay)
        self.assertEqual(json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))["last_seen_version"],
                         json.loads(paths.VERSION_FILE.read_text(encoding="utf-8"))["version"])
        g.scenes.stack.clear()
        g.scenes.push(MenuScene(g))
        g.scenes.flush()
        self.assertNotIsInstance(g.scenes.current, NewsOverlay)              # 2ª vez: não mostra

    def test_background_update_notice(self):
        from network.updater import UpdateInfo
        g = self.game

        class FakeTask:
            state = "available"
            info = UpdateInfo("99.0.0", "", "", "")
        g.headless = False
        try:
            g.update_notice, g._bg_task = None, FakeTask()
            g._background_update(0.1)
            self.assertEqual(g.update_notice, "99.0.0")
            self.assertTrue(any("99.0.0" in t.msg for t in g.feedback.toasts))
            g._background_update(0.1)                                         # já avisou: não repete nem busca de novo
        finally:
            g.headless = True
            g.update_notice, g._bg_task = None, None

    def test_options_all_tabs_and_new_actions(self):
        from scenes.integrity import IntegrityOverlay, RepairScene
        from scenes.options import TABS, OptionsScene
        g = self.game
        self.assertEqual(len(TABS), 6)
        for tab in range(len(TABS)):
            o = OptionsScene(g, tab)
            for r in o.rows:
                self.assertLess(r.rect.bottom, 720, (tab, r.label))           # nenhuma linha sai da tela
            self._run(o, 20)
        o = OptionsScene(g, 4)
        o._sysinfo()
        o._set("language", "en")
        o._set("accessibility.colorblind", True)
        o._reset_tab()
        o.tab = 3
        o._build()
        o._reset_tab()
        self.assertEqual(i18n.language(), "pt-BR")
        self.assertFalse(ui.colorblind)
        ov = IntegrityOverlay(g)
        self._run(ov, 10)
        for _ in range(100):                                                  # espera a thread terminar
            if ov.task.result or ov.task.error:
                break
            pygame.time.wait(20)
        self._run(ov, 20)
        self.assertEqual(ov.task.result["state"], "nomanifest")               # rodando do código-fonte
        from unittest import mock
        from network import release_tools as rt
        with mock.patch.object(rt, "get_text", side_effect=OSError("sem rede")):     # sem rede nos testes
            rep = RepairScene(g)
            self._run(rep, 5)
            for _ in range(100):
                if rep.task.state == "error":
                    break
                pygame.time.wait(20)
            self._run(rep, 5)
        self.assertEqual(rep.task.state, "error")

    def test_stat_icons_and_scenery_in_screens(self):
        from minigames import REGISTRY
        from scenes.collection import CollectionScene
        from scenes.stats import StatsScene
        g = self.game
        settings.set_value("accessibility.colorblind", True)
        g.apply_settings()
        for cls in REGISTRY.values():
            self._run(cls(g), 30)
        self._run(StatsScene(g), 10)
        sel = CollectionScene(g)
        self._run(sel, 40)
        self.assertLess(sel.drawn, 60)


if __name__ == "__main__":
    unittest.main()
