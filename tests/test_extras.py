"""Loja, tutorial, modo atração, reverter vídeo, árvore de conquistas, rollback do atualizador."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from core.engine import Game  # noqa: E402
from entities.progression import Profile  # noqa: E402
from network import release_tools as rt  # noqa: E402


class ShopTest(unittest.TestCase):
    def test_buy_equip_and_persist(self):
        from scenes import shop
        p = Profile(gold=100)
        self.assertEqual(shop.buy_or_equip(p, "hit_emerald"), "bought")
        self.assertEqual(p.gold, 40)
        self.assertEqual(shop.buy_or_equip(p, "hit_emerald"), "equipped")
        self.assertEqual(shop.buy_or_equip(p, "hit_rainbow"), "poor")
        q = Profile.from_dict(p.to_dict())
        self.assertEqual(q.equipped["fx_hit"], "hit_emerald")
        self.assertIn("hit_emerald", q.cosmetics)
        self.assertIsNone(shop.color_of(""))
        self.assertEqual(len(shop.color_of("hit_rainbow", 1.0)), 3)


class SceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = Game(headless=True)
        cls.game.profile = Profile(gold=500)

    def _draw(self, sc, frames=3):
        s = pygame.Surface((1280, 720))
        for _ in range(frames):
            sc.update(1 / 60)
            sc.draw(s)

    def test_shop_and_hub_draw(self):
        from scenes.hub import HubScene
        from scenes.shop import ShopScene
        sc = ShopScene(self.game)
        sc._pick(sc.mine[1])
        sc._set_slot(1)
        self._draw(sc)
        self._draw(HubScene(self.game))

    def test_tutorial_progresses_with_real_actions(self):
        from scenes.tutorial import STEPS, TutorialScene
        sc = TutorialScene(self.game)
        inp = self.game.input
        for action, need, _ in STEPS:
            for _ in range(need):
                inp._pressed.add(action)
                sc.update(1 / 60)
                inp._pressed.clear()
        self.assertEqual(sc.step, len(STEPS))
        self._draw(sc)

    def test_attract_runs_without_touching_the_save(self):
        from scenes.attract import AttractScene
        self.game.profile = None
        sc = AttractScene(self.game)
        s = pygame.Surface((1280, 720))
        for _ in range(600):
            sc.update(1 / 60)
        sc.draw(s)
        sc.exit()
        self.assertIsNone(self.game.profile)
        self.game.profile = Profile(gold=500)

    def test_revert_overlay_undoes_after_timeout(self):
        from scenes.options import RevertOverlay
        calls = []
        r = RevertOverlay(self.game, lambda: calls.append("undo"), lambda: calls.append("after"))
        self.game.scenes.push(r)
        self.game.scenes.flush()
        r.left = 0.01
        r.update(0.05)
        self.assertEqual(calls, ["undo", "after"])

    def test_achievement_tree_chains_share_a_row(self):
        from scenes.achievements_screen import AchievementsScene
        sc = AchievementsScene(self.game)
        self.assertEqual(sc.pos["first_blood"][0], sc.pos["ten_wins"][0])
        self.assertLess(sc.pos["first_blood"][1], sc.pos["fifty_wins"][1])
        self._draw(sc, 1)

    def test_options_all_tabs_fit_on_screen(self):
        from scenes.options import TABS, OptionsScene
        for tab in range(len(TABS)):
            o = OptionsScene(self.game, tab)
            self._draw(o, 1)
            for r in o.rows:
                self.assertLessEqual(r.rect.bottom, 720, (tab, r.label))


class RollbackTest(unittest.TestCase):
    def test_install_makes_backup_and_rollback_restores(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old, new, target = root / "old", root / "new", root / "game"
            for folder, ver in ((old, "1"), (new, "2")):
                folder.mkdir()
                (folder / "a.txt").write_text("A" + ver)
                (folder / "b.txt").write_text("B" + ver)
                if ver == "2":
                    (folder / "c.txt").write_text("C2")
                rt.write_manifest(folder, ver)
            rt.install_tree(old, target, lambda m: None)
            self.assertFalse(rt.has_backup(target))                # 1ª instalação: nada a guardar
            rt.install_tree(new, target, lambda m: None)
            self.assertTrue(rt.has_backup(target))
            self.assertEqual((target / "a.txt").read_text(), "A2")
            self.assertTrue(rt.rollback(target, lambda m: None))
            self.assertEqual((target / "a.txt").read_text(), "A1")
            self.assertFalse((target / "c.txt").exists())
            self.assertFalse(rt.has_backup(target))


if __name__ == "__main__":
    unittest.main()


class McManifestTest(unittest.TestCase):
    def test_manifest_matches_files(self):
        import json
        from tools.make_mc_manifest import ROOT, build
        saved = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, build(), "rode: python tools/make_mc_manifest.py")
