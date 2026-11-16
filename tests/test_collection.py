"""Steve como lutador fixo, raridades, desafios de lendas, coleção e aparências."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from entities import roster  # noqa: E402
from entities.progression import Profile  # noqa: E402


class RarityDataTest(unittest.TestCase):
    def test_every_character_has_valid_rarity(self):
        order = set(roster.rarity_order())
        for c in roster.characters():
            self.assertIn(c.get("rarity"), order, c["id"])

    def test_ladder_rarity_grows_and_boss_is_legendary(self):
        order = roster.rarity_order()
        ranks = [order.index(roster.rarity(e["character"])) for e in roster.enemies()]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(roster.rarity(roster.enemies()[-1]["character"]), "lendario")

    def test_tiers_unlock_with_arena_stage(self):
        p = Profile()
        self.assertTrue(roster.tier_unlocked(p, "comum"))
        self.assertFalse(roster.tier_unlocked(p, "incomum"))
        p.arena_stage = 4
        self.assertTrue(roster.tier_unlocked(p, "raro"))
        self.assertFalse(roster.tier_unlocked(p, "lendario"))
        p.arena_stage = len(roster.enemies())
        self.assertTrue(all(roster.tier_unlocked(p, t) for t in roster.rarity_order()))

    def test_challenge_edef_scales_with_rarity_and_is_deterministic(self):
        by = {}
        for c in roster.characters():
            by.setdefault(c["rarity"], c["id"])
        hp = {r: roster.challenge_edef(cid)["hp"] for r, cid in by.items()}
        self.assertEqual(roster.challenge_edef(by["raro"]), roster.challenge_edef(by["raro"]))
        self.assertLess(hp["comum"], hp["raro"])
        self.assertLess(hp["raro"], hp["lendario"])
        e = roster.challenge_edef(by["epico"])
        self.assertEqual(e["character"], by["epico"])
        self.assertTrue(e["attacks"])


class SteveAndSkinsTest(unittest.TestCase):
    def test_default_player_is_steve(self):
        p = Profile()
        self.assertEqual(roster.character(p.character)["name"], "Steve")
        f = roster.build_player(p, 0, 0)
        self.assertEqual(f.name, "Steve")

    def test_old_save_with_ucdm_fighter_becomes_steve(self):
        p = Profile.from_dict({"character": "kozu", "gold": 5, "stats": {}})
        self.assertEqual(p.character, "steve")
        self.assertEqual(p.gold, 5)

    def test_collection_roundtrip(self):
        p = Profile()
        p.collection = {"skeleto": 2}
        self.assertEqual(Profile.from_dict(p.to_dict()).collection, {"skeleto": 2})

    def test_skin_unlock_conditions(self):
        p = Profile()
        by = {s["id"]: s for s in roster.skins()}
        self.assertTrue(roster.unlocked_skin(p, by["steve"]))
        self.assertFalse(roster.unlocked_skin(p, by["alex"]))
        p.wins = 3
        self.assertTrue(roster.unlocked_skin(p, by["alex"]))
        p.collection = {c["id"]: 1 for c in roster.characters()[:25]}
        self.assertTrue(roster.unlocked_skin(p, by["kai"]))
        self.assertFalse(roster.unlocked_skin(p, by["sunny"]))
        legend = next(c["id"] for c in roster.characters() if c["rarity"] == "lendario")
        p.collection[legend] = 1
        self.assertTrue(roster.unlocked_skin(p, by["sunny"]))

    def test_skin_sprites_exist_and_pixel_scale_is_integer(self):
        from systems.assets import AssetManager
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        a = AssetManager()
        for s in roster.skins():
            img = a.image_h(s["sprite"], 230)
            self.assertEqual(img.get_height() % 32, 0, s["id"])
            self.assertEqual(img.get_width() * 2, img.get_height())


class CollectionFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        cls.game = Game(headless=True)

    def setUp(self):
        self.game.profile = Profile()

    def _arena(self, challenger):
        from scenes.arena import ArenaScene
        return ArenaScene(self.game, 0, challenger=challenger)

    def test_challenge_win_adds_card_once_with_full_gold(self):
        cid = next(c["id"] for c in roster.characters() if c["rarity"] == "comum" and c["id"] not in
                   {e["character"] for e in roster.enemies()})
        a = self._arena(cid)
        a.result = "win"
        a._finish()
        p = self.game.profile
        self.assertEqual(p.collection[cid], 1)
        self.assertEqual(p.arena_stage, 0)             # desafio não avança a escada
        gold1 = p.gold
        self.assertGreaterEqual(gold1, roster.rarity_info("comum")["gold"])
        b = self._arena(cid)
        b.result = "win"
        b._finish()
        self.assertEqual(p.collection[cid], 2)
        self.assertLess(p.gold - gold1, gold1)         # repetição rende menos

    def test_ladder_win_registers_collection_and_advances(self):
        a = self._arena(None)
        a.result = "win"
        a._finish()
        p = self.game.profile
        self.assertEqual(p.arena_stage, 1)
        self.assertIn(roster.enemies()[0]["character"], p.collection)

    def test_collection_scene_modes_and_locks(self):
        from scenes.collection import CollectionScene
        sc = CollectionScene(self.game)
        surf = pygame.Surface((1280, 720))
        sc.draw(surf)
        self.assertLess(sc.drawn, 60)                  # culling
        # lenda de raridade bloqueada não inicia desafio
        sc.filter = len(roster.rarity_order())
        sc._cycle_filter()                             # volta a "todas"
        sc.filter = 4
        sc._cycle_filter()                             # 5 = lendário
        sc.index = 0
        sc._act()
        self.assertGreater(sc.toast[1], 0)
        sc._toggle_mode()
        self.assertEqual(sc.mode, "skins")
        sc.draw(surf)
        alex = next(i for i, s in enumerate(sc.items) if s["id"] == "alex")
        sc.index = alex
        sc._act()
        self.assertEqual(self.game.profile.character, "steve")     # bloqueada: não troca
        self.game.profile.wins = 3
        sc._act()
        self.assertEqual(self.game.profile.character, "alex")


if __name__ == "__main__":
    unittest.main()


class AlbumSearchTest(unittest.TestCase):
    def test_busca_filtra_por_nome(self):
        from core.engine import Game
        from scenes.collection import CollectionScene
        game = Game(headless=True)
        game.profile = Profile()
        sc = CollectionScene(game)
        total = len(sc.items)
        sc.query = sc.items[0]["name"][:3].lower()
        sc._rebuild()
        self.assertTrue(0 < len(sc.items) <= total)
        sc.query = "zzzzzz"
        sc._rebuild()
        self.assertEqual(sc.items, [])
