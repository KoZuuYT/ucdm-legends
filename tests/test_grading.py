"""Nota e dicas pós-luta, efeitos de partícula de Minecraft e menu."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from systems import grading  # noqa: E402

GOOD = dict(won=True, time=20, par_time=40, hp_frac=0.95, parries=4, perfect_dodges=3)
BAD = dict(won=True, time=120, par_time=40, hp_frac=0.05, parries=0, perfect_dodges=0)


class GradingTest(unittest.TestCase):
    def test_grade_ordering(self):
        self.assertEqual(grading.grade(GOOD), "S")
        self.assertEqual(grading.grade(BAD), "D")
        mid = dict(GOOD, hp_frac=0.6, parries=1, perfect_dodges=0, time=45)
        self.assertIn(grading.grade(mid), ("B", "C"))
        self.assertEqual(grading.grade(dict(GOOD, won=False)), "D")

    def test_reaction_plays_raise_grade(self):
        base = dict(won=True, time=40, par_time=40, hp_frac=0.6, parries=0, perfect_dodges=0)
        better = dict(base, parries=5)
        order = grading.GRADES
        self.assertGreater(order.index(grading.grade(better)), order.index(grading.grade(base)))

    def test_hints_are_relevant_and_limited(self):
        h = grading.hints(dict(won=False, guardbreaks_taken=3, unblockable_taken=1, fatigue_peak=4, parries=0,
                               perfect_dodges=0, taken=50, dodges=0), limit=2)
        self.assertEqual(len(h), 2)
        self.assertTrue(any("laranja" in x for x in h))
        self.assertEqual(grading.hints(dict(won=True, parries=3, perfect_dodges=2, dodges=4)), [])


class FightStatsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        cls.game = Game(headless=True)

    def test_arena_counts_and_shows_grade(self):
        from entities.progression import Profile
        from scenes.arena import ArenaScene
        from scenes.results import ResultsOverlay
        self.game.profile = Profile()
        a = ArenaScene(self.game, 0)
        a.st.update(parries=3, perfect_dodges=2, dodges=3, hits_landed=8)
        a.now = 15.0
        a.result = "win"
        self.game.scenes.stack.clear()
        self.game.scenes.push(a)
        self.game.scenes.flush()
        a._finish()
        self.game.scenes.flush()
        top = self.game.scenes.current
        self.assertIsInstance(top, ResultsOverlay)
        self.assertIn(top.grade, grading.GRADES)
        self.assertTrue(any(l.startswith("Nota:") for l in top.lines))
        surf = pygame.Surface((1280, 720))
        for _ in range(80):
            top.update(1 / 60)
        top.draw(surf)

    def test_defeat_shows_hint_not_grade(self):
        from entities.progression import Profile
        from scenes.arena import ArenaScene
        self.game.profile = Profile()
        a = ArenaScene(self.game, 0)
        a.st.update(guardbreaks_taken=3, taken=70)
        a.result = "lose"
        self.game.scenes.stack.clear()
        self.game.scenes.push(a)
        self.game.scenes.flush()
        a._finish()
        self.game.scenes.flush()
        top = self.game.scenes.current
        self.assertIsNone(top.grade)
        self.assertTrue(any("laranja" in l for l in top.lines))


class McParticleTest(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.display.set_mode((64, 64))

    def test_anim_and_icons_spawn_update_and_expire(self):
        from systems.particles import ParticleSystem
        fx = ParticleSystem(50)
        fx.anim(100, 100, "particle/sweep", 8, k=4, tint=(255, 200, 100))
        fx.icons(100, 100, "particle/critical_hit.png", n=6, tint=(255, 215, 90))
        self.assertGreater(len(fx.sprs.active), 1)
        surf = pygame.Surface((300, 300))
        fx.draw(surf)
        for _ in range(120):
            fx.update(1 / 60)
        self.assertEqual(len(fx.sprs.active), 0)
        fx.anim(1, 1, "particle/nao_existe", 4)          # sem assets: não quebra
        fx.scale = 0.0
        fx.anim(1, 1, "particle/sweep", 8)
        self.assertEqual(len(fx.sprs.active), 0)

    def test_menu_renders_panorama_in_minecraft_theme(self):
        from core import theme
        from core.engine import Game
        g = Game(headless=True)
        from scenes.menu import MenuScene
        theme.set_theme("minecraft")
        try:
            m = MenuScene(g)
            surf = pygame.Surface((1280, 720))
            for _ in range(5):
                m.update(1 / 60)
                m.draw(surf)
            self.assertGreater(len(m.splash_text), 3)
        finally:
            theme.set_theme("torneio")


if __name__ == "__main__":
    unittest.main()
