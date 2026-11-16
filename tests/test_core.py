"""Testes headless (rodam no CI sem janela/som): python -m unittest discover -s tests -v"""
import os
import random
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_TMP = tempfile.mkdtemp(prefix="ucdm-test-")
os.environ["UCDM_USER_DIR"] = _TMP          # nunca toca no save real
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from network import release_tools as rt  # noqa: E402


class ReleaseToolsTest(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(rt.is_newer("0.2.0", "0.1.9"))
        self.assertTrue(rt.is_newer("v1.0", "0.9.9"))
        self.assertFalse(rt.is_newer("0.1.0", "0.1.0"))
        self.assertFalse(rt.is_newer("0.1.0-beta", "0.1.0"))

    def test_url_allowlist(self):
        with self.assertRaises(ValueError):
            rt._check_url("http://github.com/x")          # sem https
        with self.assertRaises(ValueError):
            rt._check_url("https://evil.example.com/a.zip")
        rt._check_url("https://github.com/a/b/releases/download/v1/x.zip")

    def test_zip_slip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            z = Path(d) / "bad.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("../evil.txt", "x")
            with self.assertRaises(ValueError):
                rt.safe_extract(z, Path(d) / "out")

    def test_sha_and_install_tree(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            old, new, target = d / "old", d / "new", d / "target"
            for root, files in ((old, {"a.txt": "1", "gone.txt": "x"}), (new, {"a.txt": "2", "sub/b.txt": "3"})):
                for rel, txt in files.items():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (root / rel).write_text(txt)
                rt.write_manifest(root, "1")
            rt.install_tree(old, target, log=lambda m: None)
            (target / "save_do_jogador.json").write_text("keep")   # fora do manifest: preservado
            rt.install_tree(new, target, log=lambda m: None)
            self.assertEqual((target / "a.txt").read_text(), "2")
            self.assertTrue((target / "sub/b.txt").exists())
            self.assertFalse((target / "gone.txt").exists())
            self.assertTrue((target / "save_do_jogador.json").exists())
            f = d / "f.bin"
            f.write_bytes(b"abc")
            rt.verify_sha256(f, rt.sha256_file(f) + "  f.bin")
            with self.assertRaises(ValueError):
                rt.verify_sha256(f, "0" * 64)


class SystemsTest(unittest.TestCase):
    def test_spatial_grid(self):
        from systems.culling import SpatialGrid
        g = SpatialGrid(cell=100)
        objs = [object() for _ in range(500)]
        rnd = random.Random(1)
        rects = {}
        for o in objs:
            r = pygame.Rect(rnd.randint(0, 5000), rnd.randint(0, 5000), 30, 30)
            rects[o] = r
            g.insert(o, r)
        view = pygame.Rect(1000, 1000, 1280, 720)
        got = set(g.query(view))
        expected = {o for o, r in rects.items() if r.colliderect(view)}
        self.assertEqual(got, expected)
        o = objs[0]
        g.move(o, pygame.Rect(1100, 1100, 30, 30))
        self.assertIn(o, g.query(view))
        g.remove(o)
        self.assertNotIn(o, g.query(view))

    def test_pool(self):
        from systems.pool import Pool
        p = Pool(dict, 2, grow=False)
        a, b = p.spawn(), p.spawn()
        self.assertIsNone(p.spawn())
        p.release(a)
        self.assertIs(p.spawn(), a)
        p.release_where(lambda o: o is b)
        self.assertEqual(len(p), 1)

    def test_profile(self):
        from entities.progression import Profile
        p = Profile(character="kozu")
        gained = p.stats["strength"].add_xp(10_000)
        self.assertGreater(gained, 3)
        p2 = Profile.from_dict(p.to_dict())
        self.assertEqual(p2.level("strength"), p.level("strength"))


class GameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        from entities.progression import Profile
        cls.game = Game(headless=True)
        cls.game.profile = Profile(character="kozu")

    def _run(self, scene, frames=240, keys=()):
        g = self.game
        g.scenes.stack.clear()
        g.scenes.push(scene)
        rnd = random.Random(0)
        for i in range(frames):
            g.input.begin_frame(g.time)
            if keys and i % 7 == 0:
                k = rnd.choice(keys)
                g.input.process(pygame.event.Event(pygame.KEYDOWN, key=k))
                g.input.process(pygame.event.Event(pygame.KEYUP, key=k))
            g.scenes.update(1 / 60)
            g.time += 1 / 60
            g.screen.fill((0, 0, 0))
            g.scenes.draw(g.screen)

    def test_fighter_rules(self):
        from entities import roster
        from entities.fighter import AttackDef
        p = roster.build_player(self.game.profile, 0, 0)
        e = roster.build_enemy(roster.enemies()[0], 100, 0)
        atk = AttackDef(windup=0.1, active=0.1, recover=0.1)
        p.set_block(True, now=10.0)
        self.assertEqual(p.receive(atk, e, now=10.05).outcome, "parry")
        r = p.receive(atk, e, now=11.0)
        self.assertEqual(r.outcome, "block")
        self.assertLess(r.damage, e.damage)
        p.set_block(False, 11.0)
        unb = AttackDef(unblockable=True)
        p.set_block(True, now=12.0)
        self.assertIn(p.receive(unb, e, now=12.01).outcome, ("hit", "crit"))

    def test_scenes_smoke(self):
        from minigames import REGISTRY
        from scenes.arena import ArenaScene
        from scenes.character_select import CharacterSelectScene
        from scenes.hub import HubScene
        from scenes.menu import MenuScene
        keys = (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_j, pygame.K_k, pygame.K_l)
        for cls in REGISTRY.values():
            with self.subTest(minigame=cls.key):
                self._run(cls(self.game), 60 * 50, keys)   # partida inteira
        self._run(ArenaScene(self.game, 0), 60 * 30, keys)
        self._run(HubScene(self.game), 30)
        self._run(MenuScene(self.game), 30)
        sel = CharacterSelectScene(self.game, new_game=False)
        self._run(sel, 120, (pygame.K_DOWN,))
        self.assertLess(sel.drawn, 60)   # culling: nunca desenha os 160


if __name__ == "__main__":
    unittest.main()
