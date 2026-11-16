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


class AchievementsAndEndlessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        cls.game = Game(headless=True)

    def test_achievements_unlock_once_and_persist(self):
        from entities.progression import Profile
        from systems import achievements
        p = Profile()
        self.assertEqual(achievements.check(p), [])
        p.wins = 1
        new = achievements.check(p)
        self.assertEqual([d["id"] for d in new], ["first_blood"])
        self.assertEqual(achievements.check(p), [])                       # não repete
        p.counters["parries"] = 60
        ids = [d["id"] for d in achievements.check(p)]
        self.assertIn("parry_5", ids)
        self.assertIn("parry_50", ids)
        q = Profile.from_dict(p.to_dict())
        self.assertEqual(q.achievements, p.achievements)
        cur, need = achievements.progress(p, achievements.defs()[3])
        self.assertLessEqual(cur, need)

    def test_all_achievements_reference_existing_icons(self):
        from core import mcassets as mc
        for d in __import__("systems.achievements", fromlist=["defs"]).defs():
            self.assertIsNotNone(mc.load(f"item/{d['icon']}.png"), d["id"])

    def test_screens_render(self):
        from entities.progression import Profile
        from scenes.achievements_screen import AchievementsScene
        from scenes.stats import StatsScene
        self.game.profile = Profile()
        self.game.profile.history = ["W", "L", "W"]
        surf = pygame.Surface((1280, 720))
        for cls in (AchievementsScene, StatsScene):
            sc = cls(self.game)
            for _ in range(10):
                sc.update(1 / 60)
            sc.draw(surf)

    def test_endless_waves_scale_and_use_rarity_bands(self):
        import random
        from entities import roster
        rng = random.Random(1)
        self.assertEqual(roster.endless_rarity(1), "comum")
        self.assertEqual(roster.endless_rarity(5), "raro")
        self.assertEqual(roster.endless_rarity(99), "lendario")
        c1 = roster.endless_pick(1, rng)
        e1 = roster.endless_edef(1, c1)
        e9 = roster.endless_edef(9, roster.endless_pick(9, rng))
        self.assertGreater(e9["hp"], e1["hp"])
        self.assertGreater(e9["gold"], e1["gold"])
        self.assertNotEqual(roster.endless_pick(3, rng, avoid=c1), None)

    def test_endless_win_chains_to_next_wave_and_records(self):
        from entities import roster
        from entities.progression import Profile
        from scenes.arena import ArenaScene
        from scenes.results import ResultsOverlay
        self.game.profile = Profile()
        a = ArenaScene(self.game, 0, challenger=roster.endless_pick(1, __import__("random").Random(2)), endless=1)
        a.result = "win"
        self.game.scenes.stack.clear()
        self.game.scenes.push(a)
        self.game.scenes.flush()
        a._finish()
        self.game.scenes.flush()
        top = self.game.scenes.current
        self.assertIsInstance(top, ResultsOverlay)
        self.assertEqual(self.game.profile.counters["endless_best"], 1)
        top._close()
        for _ in range(3):
            self.game.scenes.flush()
        cur = self.game.scenes.current
        for _ in range(60):
            self.game.scenes.update(1 / 60)
        self.assertIsInstance(self.game.scenes.current, ArenaScene)
        self.assertEqual(self.game.scenes.current.endless, 2)


class DailyChallengeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        cls.game = Game(headless=True)

    def test_daily_is_deterministic_and_respects_unlocked_tiers(self):
        from entities import roster
        from entities.progression import Profile
        p = Profile()
        a = roster.daily(p, 20261116)
        self.assertEqual(a, roster.daily(p, 20261116))
        self.assertEqual(roster.rarity(a[0]), "comum")             # só raridades abertas
        seen = {roster.daily(p, 20260101 + i)[1]["id"] for i in range(40)}
        self.assertGreater(len(seen), 2)                          # os modificadores variam por dia

    def test_daily_modifiers_apply_and_reward_once_per_day(self):
        from entities import roster
        from entities.progression import Profile
        from scenes.arena import ArenaScene
        mods = {m["id"]: m for m in __import__("core.config", fromlist=["load"]).load("daily")["modifiers"]}
        self.game.profile = Profile()
        cid, _ = roster.daily(self.game.profile)
        base = ArenaScene(self.game, 0, challenger=cid)
        tank = ArenaScene(self.game, 0, challenger=cid, daily=mods["tank"])
        glass = ArenaScene(self.game, 0, challenger=cid, daily=mods["glass"])
        self.assertAlmostEqual(tank.enemy.max_hp, base.enemy.max_hp * 2)
        self.assertAlmostEqual(glass.player.hp, glass.player.max_hp * 0.5)
        gains = []
        for _ in range(2):
            a = ArenaScene(self.game, 0, challenger=cid, daily=mods["brute"])
            a.result = "win"
            self.game.scenes.stack.clear()
            self.game.scenes.push(a)
            self.game.scenes.flush()
            before = self.game.profile.gold
            a._finish()
            gains.append(self.game.profile.gold - before)
        self.assertGreater(gains[0], gains[1])                    # 2ª vez no dia rende menos
        self.assertEqual(self.game.profile.counters["dailies"], 1)
