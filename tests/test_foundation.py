"""Fundação do overhaul de design: tween/mola/sequência, assets de Minecraft (9-slice), tema e HUD MC."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from core import mcassets as mc  # noqa: E402
from core import mcui, theme  # noqa: E402
from systems import tween  # noqa: E402


class TweenExtrasTest(unittest.TestCase):
    def test_all_eases_hit_endpoints(self):
        for name, fn in tween.EASES.items():
            with self.subTest(ease=name):
                self.assertAlmostEqual(fn(0.0), 0.0, places=6)
                self.assertAlmostEqual(fn(1.0), 1.0, places=6)

    def test_stagger_orders_items(self):
        a, b = tween.staged(0.2, 0), tween.staged(0.2, 3)
        self.assertGreater(a, b)
        self.assertEqual(tween.staged(0.0, 2), 0.0)

    def test_spring_settles_without_overshooting_much(self):
        s = tween.Spring(0.0)
        s.target = 100.0
        peak = 0.0
        for _ in range(300):
            peak = max(peak, s.update(1 / 60))
        self.assertTrue(s.settled)
        self.assertLess(peak, 101.0)      # criticamente amortecida
        s.snap(5)
        self.assertEqual(s.value, 5)

    def test_seq_runs_steps_in_order_and_finishes(self):
        log = []
        seq = tween.Seq().at(0.0, 0.2, lambda p: log.append(("a", p))).at(0.2, 0.2, lambda p: log.append(("b", p)))
        self.assertAlmostEqual(seq.length, 0.4)
        done = False
        for _ in range(40):
            done = seq.update(0.01)
        self.assertTrue(done)
        self.assertEqual(log[-1][0], "b")
        self.assertAlmostEqual(log[-1][1], 1.0)
        seq2 = tween.Seq().at(0, 1, lambda p: None)
        seq2.skip()
        self.assertTrue(seq2.update(0))


class McAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))

    def test_assets_present(self):
        self.assertTrue(mc.available())
        for rel in (mcui.BTN, mcui.BTN_HI, mcui.BTN_OFF, mcui.POPUP, mcui.HEART + "full.png", mcui.HUD + "food_full.png",
                    mcui.HUD + "armor_full.png", mcui.BOSS + "red_progress.png", mcui.BOSS + "notched_20_progress.png"):
            self.assertIsNotNone(mc.load(rel), rel)

    def test_integer_scale_is_nearest(self):
        base = mc.load(mcui.HEART + "full.png")
        big = mc.sprite(mcui.HEART + "full.png", 3)
        self.assertEqual(big.get_size(), (base.get_width() * 3, base.get_height() * 3))
        self.assertEqual(big.get_at((4, 4)), base.get_at((1, 1)))

    def test_nine_slice_keeps_corners_and_any_size(self):
        base = mc.load(mcui.BTN)
        for size in ((120, 40), (300, 60), (50, 20), (14, 14)):
            img = mc.nine(mcui.BTN, size, 2)
            self.assertEqual(img.get_size(), size)
        img = mc.nine(mcui.BTN, (300, 60), 3)
        self.assertEqual(img.get_at((0, 0)), base.get_at((0, 0)))                 # canto preservado
        self.assertEqual(img.get_at((299, 59)), base.get_at((199, 19)))
        self.assertEqual(mc._border(mcui.BTN), (3, 3, 3, 3))

    def test_missing_asset_is_none_not_error(self):
        self.assertIsNone(mc.load("gui/nao_existe.png"))
        self.assertIsNone(mc.nine("gui/nao_existe.png", (10, 10)))


class ThemeAndHudTest(unittest.TestCase):
    def setUp(self):
        pygame.font.init()
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        self.addCleanup(theme.set_theme, "torneio")

    def test_theme_switch_and_fallback(self):
        theme.set_theme("minecraft")
        self.assertTrue(theme.mc())
        theme.set_theme("inexistente")
        self.assertEqual(theme.name, "torneio")
        self.assertFalse(theme.mc())

    def test_hearts_draw_full_half_empty(self):
        surf = pygame.Surface((400, 60), pygame.SRCALPHA)
        self.assertTrue(mcui.hearts(surf, 0, 0, 0.55, k=3))
        full = mc.sprite(mcui.HEART + "full.png", 3)
        # 55% = 5 cheios + 1 meio -> o 5º (índice 4) está cheio e o 7º (índice 6) vazio
        self.assertEqual(surf.get_at((4 * 24 + 12, 12)), full.get_at((12, 12)))
        self.assertNotEqual(surf.get_at((6 * 24 + 12, 12)), full.get_at((12, 12)))

    def test_boss_bar_crops_by_fraction(self):
        surf = pygame.Surface((200, 20), pygame.SRCALPHA)
        self.assertTrue(mcui.boss_bar(surf, pygame.Rect(0, 0, 200, 10), 0.5, "red", notches=10))
        self.assertTrue(mcui.boss_bar(surf, pygame.Rect(0, 0, 200, 10), 1.0, "purple", notches=20, rtl=True))

    def test_buttons_and_panels_render_in_both_themes(self):
        from core import ui
        for name in ("torneio", "minecraft"):
            theme.set_theme(name)
            surf = pygame.Surface((400, 200))
            font = pygame.font.Font(None, 28)
            b = ui.Button((20, 20, 200, 50), "Teste", lambda: None, sub="sub")
            b.draw(surf, font, True, font)
            b.enabled = False
            b.draw(surf, font, False, font)
            ui.panel(surf, (10, 90, 300, 80))


if __name__ == "__main__":
    unittest.main()


class CompatTest(unittest.TestCase):
    def test_frect_fallback_matches_pygame_frect(self):
        from core import compat
        fb = compat._FRectFallback
        a, b = fb(10.5, 20.25, 30, 40), pygame.FRect(10.5, 20.25, 30, 40)
        self.assertEqual((a.x, a.y, a.w, a.h), (b.x, b.y, b.w, b.h))
        self.assertEqual((a.right, a.bottom, a.center), (b.right, b.bottom, b.center))
        self.assertEqual(tuple(a.inflate(10, 6)), tuple(b.inflate(10, 6)))
        self.assertEqual(a.colliderect(fb(30, 30, 50, 50)), b.colliderect(pygame.FRect(30, 30, 50, 50)))
        self.assertFalse(a.colliderect(fb(100, 100, 5, 5)))
        a.center = (0, 0)
        b.center = (0, 0)
        self.assertEqual(tuple(a), tuple(b))
        v1, v2 = fb(0, 0, 100, 50), pygame.FRect(0, 0, 100, 50)
        world = (0, 0, 80, 200)
        v1.clamp_ip(fb(*world))
        v2.clamp_ip(pygame.FRect(*world))
        self.assertEqual(tuple(v1), tuple(v2))
        self.assertEqual(tuple(fb(a)), tuple(a))            # construção a partir de outro retângulo
