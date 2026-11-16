"""Testes do update de combate/feedback/entrada: cliques que "não pegavam", teclas padrão, janela sem barras pretas,
contra-ataque, fadiga, armadura, intro de batalha e UI animada (headless)."""
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())
os.environ.setdefault("UCDM_USER_DIR", tempfile.mkdtemp(prefix="ucdm-test-combat-"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from core import ui  # noqa: E402
from core.input import InputManager, pretty_key  # noqa: E402


class FakeDisplay:
    def window_to_virtual(self, x, y):
        return x, y

    def normalized_to_virtual(self, x, y):
        return x, y


class InputRegressionTest(unittest.TestCase):
    def setUp(self):
        self.im = InputManager(FakeDisplay(), {"attack": ["mouse1", "j"], "block": ["f"], "dodge": ["left shift"],
                                               "confirm": ["return"]})
        self.im.set_time(0.0)

    def ev(self, t, **kw):
        self.im.process(pygame.event.Event(t, **kw))

    def test_press_survives_frames_without_a_logic_step(self):
        """Bug: com fps > 60 havia frames sem passo de lógica e o clique/tecla era descartado."""
        self.ev(pygame.KEYDOWN, key=pygame.K_RETURN)
        self.im.set_time(0.007)                  # frame seguinte, ainda sem passo de lógica: NÃO descarta
        self.im.set_time(0.014)
        self.assertTrue(self.im.pressed("confirm"))
        self.im.consume_step()                   # um passo de lógica viu a entrada
        self.assertFalse(self.im.pressed("confirm"))

    def test_click_survives_and_is_tolerant_to_small_slips(self):
        self.ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        self.ev(pygame.MOUSEBUTTONUP, button=1, pos=(100 + 40, 100 + 20))   # mão escorregou 40 px: ainda é clique
        self.im.set_time(0.01)
        self.assertEqual(self.im.taps, [(140, 120)])
        self.im.consume_step()
        self.assertEqual(self.im.taps, [])
        self.ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        self.ev(pygame.MOUSEBUTTONUP, button=1, pos=(300, 100))             # arrasto longo não é clique
        self.assertEqual(self.im.taps, [])

    def test_left_mouse_button_is_the_attack_action(self):
        self.ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))
        self.assertTrue(self.im.pressed("attack") and self.im.held("attack"))
        self.ev(pygame.MOUSEBUTTONUP, button=1, pos=(5, 5))
        self.assertFalse(self.im.held("attack"))
        self.ev(pygame.MOUSEBUTTONDOWN, button=3, pos=(5, 5))                # botão direito não está mapeado
        self.assertFalse(self.im.held("attack"))

    def test_rebind_capture_accepts_mouse_buttons(self):
        self.im.capture = True
        self.ev(pygame.MOUSEBUTTONDOWN, button=3, pos=(1, 1))
        self.assertEqual(self.im.captured, "mouse3")
        self.im.set_bindings({"block": ["mouse3"]})
        self.im.capture = False
        self.ev(pygame.MOUSEBUTTONDOWN, button=3, pos=(1, 1))
        self.assertTrue(self.im.held("block"))

    def test_scene_origin_offsets_pointer(self):
        self.im.origin_x = 160                  # layout fixo centralizado numa janela larga
        self.ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(200, 50))
        self.ev(pygame.MOUSEBUTTONUP, button=1, pos=(200, 50))
        self.assertEqual(self.im.taps, [(40, 50)])

    def test_default_keybinds_and_pretty_names(self):
        from core import config
        b = config.load("game", reload=True)["input"]
        self.assertEqual(b["attack"][0], "mouse1")
        self.assertEqual(b["block"][0], "f")
        self.assertEqual(b["dodge"][0], "left shift")
        self.assertEqual(pretty_key("mouse1"), "MOUSE ESQ.")
        self.assertEqual(pretty_key("left shift"), "SHIFT")
        self.assertEqual(pretty_key("f"), "F")


class WindowScalingTest(unittest.TestCase):
    def tearDown(self):
        pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    def _display(self):
        from core.display import Display
        pygame.init()
        return Display(1280, 720, "t", headless=False)

    def test_canvas_follows_window_aspect(self):
        d = self._display()
        pygame.display.set_mode((1920, 1080), pygame.RESIZABLE)
        d.layout()
        self.assertEqual((d.canvas_w, round(d.scale, 3), d.offset), (1280, 1.5, (0, 0)))
        pygame.display.set_mode((2560, 1080), pygame.RESIZABLE)          # ultrawide: canvas mais largo, sem barras
        self.assertTrue(d.layout())
        self.assertEqual(d.canvas_w, 1707)
        self.assertEqual(d.offset[0], 0)
        self.assertEqual(d.surface.get_size(), (1707, 720))
        pygame.display.set_mode((8000, 1000), pygame.RESIZABLE)          # absurdamente largo: limita e centraliza
        d.layout()
        self.assertEqual(d.canvas_w, 1920)

    def test_mouse_maps_to_canvas(self):
        d = self._display()
        pygame.display.set_mode((2560, 1080), pygame.RESIZABLE)
        d.layout()
        x, y = d.window_to_virtual(1280, 540)
        self.assertAlmostEqual(x, d.canvas_w / 2, delta=1)
        self.assertAlmostEqual(y, 360, delta=1)

    def test_bars_are_filled_not_black(self):
        d = self._display()
        pygame.display.set_mode((1000, 1000), pygame.RESIZABLE)          # mais estreita que 16:9: faixas em cima/baixo
        d.layout()
        self.assertGreater(d.offset[1], 0)
        d.surface.fill((200, 40, 40))
        d.present()
        win = pygame.display.get_surface()
        for pos in ((500, 3), (500, 997)):                                  # faixas esticadas, não pretas
            c = tuple(win.get_at(pos))[:3]
            self.assertTrue(all(abs(a - b) <= 6 for a, b in zip(c, (200, 40, 40))), c)

    def test_fixed_scenes_are_centered_and_margins_stretched(self):
        from core.scene import Scene, SceneManager

        seen = {}

        class Fixed(Scene):
            def draw(self, surf):
                seen["fixed"] = surf.get_size()
                surf.fill((10, 80, 200))

        class Wide(Scene):
            wide = True

            def draw(self, surf):
                seen["wide"] = surf.get_size()

        sm = SceneManager()
        canvas = pygame.Surface((1600, 720))
        sm.stack = [Fixed(None)]
        sm.draw(canvas)
        self.assertEqual(seen["fixed"], (1280, 720))
        self.assertEqual(sm.origin_x(1600), 160)
        left = canvas.get_at((5, 300))
        self.assertGreater(left[2], 60)                                 # margem azul (esticada), não preta
        sm.stack = [Wide(None)]
        sm.draw(canvas)
        self.assertEqual(seen["wide"], (1600, 720))
        self.assertEqual(sm.origin_x(1600), 0)


class CombatRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))

    def setUp(self):
        from entities import roster
        from entities.progression import Profile
        random.seed(1)
        self.p = roster.build_player(Profile(character="kozu"), 0, 0)
        self.e = roster.build_enemy(roster.enemies()[3], 100, 0)
        self.e.facing = -1

    def atk(self, **kw):
        from entities.fighter import AttackDef
        return AttackDef(windup=0.1, active=0.1, recover=0.1, **kw)

    def test_perfect_dodge_requires_late_dodge(self):
        self.p.stamina = 100
        self.assertTrue(self.p.dodge())
        self.p.timer = 0.05
        r = self.e.receive(self.atk(), self.p, 0) if False else self.p.receive(self.atk(), self.e, 0)
        self.assertEqual((r.outcome, r.perfect), ("dodge", True))
        self.p.timer = 0.25                                       # esquivou cedo demais: escapa, mas não é perfeita
        r = self.p.receive(self.atk(), self.e, 0)
        self.assertEqual((r.outcome, r.perfect), ("dodge", False))
        self.p.timer = 0.30                                       # i-frames acabaram: leva o golpe
        self.assertIn(self.p.receive(self.atk(), self.e, 0).outcome, ("hit", "crit"))

    def test_counter_attack_is_guaranteed_crit_and_consumed(self):
        self.e.max_poise = 0
        self.p.grant_counter()
        r = self.e.receive(self.atk(), self.p, 0)
        self.assertTrue(r.counter and r.outcome == "crit")
        self.assertEqual(self.p.counter_time, 0.0)
        r2 = self.e.receive(self.atk(), self.p, 0)
        self.assertFalse(r2.counter)

    def test_fatigue_reduces_damage_and_decays(self):
        self.assertEqual(self.p.fatigue_mult(), 1.0)
        self.p.fatigue = 6
        self.assertAlmostEqual(self.p.fatigue_mult(), 0.52, places=2)
        self.p.fatigue = 50
        self.assertEqual(self.p.fatigue_mult(), 0.5)             # piso
        self.p.fatigue = 4
        for _ in range(120):
            self.p.update(1 / 60, (-1e6, 1e6))
        self.assertLess(self.p.fatigue, 3)

    def test_stamina_pauses_after_spending_and_spam_runs_dry(self):
        self.p.stamina = self.p.max_stamina
        self.assertTrue(self.p.attack_cmd())
        before = self.p.stamina
        for _ in range(30):                                      # 0,5 s depois: ainda sem recuperar
            self.p.update(1 / 60, (-1e6, 1e6))
        self.assertLessEqual(self.p.stamina, before + 0.01)
        self.p.stamina = 1
        self.p._set("idle")
        self.assertFalse(self.p.attack_cmd())                    # sem estamina não ataca

    def test_armor_reduces_damage_then_breaks_and_punishes(self):
        self.e.max_poise = self.e.poise = 40
        self.e.armor = 0.4
        first = self.e.receive(self.atk(), self.p, 0)
        self.assertTrue(first.armored)
        self.assertLess(first.damage, self.p.damage)
        broke = False
        for _ in range(40):
            self.e.state = "idle"
            r = self.e.receive(self.atk(), self.p, 0)
            if r.broke:
                broke = True
                break
        self.assertTrue(broke)
        self.assertEqual(self.e.state, "stunned")
        r = self.e.receive(self.atk(), self.p, 0)
        self.assertTrue(r.punish and not r.armored)              # armadura caída: dano cheio e punição
        self.assertGreater(r.damage, first.damage)
        for _ in range(240):                                     # depois do atordoamento a armadura volta cheia
            self.e.update(1 / 60, (-1e6, 1e6))
        self.assertEqual(self.e.poise, self.e.max_poise)

    def test_guard_break_ignores_block_but_parry_beats_it(self):
        gb = self.atk(guard_break=True)
        self.p.stamina = 100
        self.p.set_block(True, 10.0)
        r = self.p.receive(gb, self.e, 10.5)                    # bloqueio "tarde": guarda quebra
        self.assertEqual(r.outcome, "guardbreak")
        self.assertEqual(self.p.state, "stunned")
        self.p._set("idle")
        self.p.stamina = 100
        self.p.set_block(True, 20.0)
        self.assertEqual(self.p.receive(gb, self.e, 20.05).outcome, "parry")   # no tempo: parry
        un = self.atk(unblockable=True)
        self.p._set("idle")
        self.p.set_block(True, 30.0)
        self.assertIn(self.p.receive(un, self.e, 30.01).outcome, ("hit", "crit"))

    def test_ai_reads_spam_and_chains(self):
        from entities.ai import EnemyBrain
        cfg = {"block_chance": 0.1, "read_spam": 0.5, "riposte": 1.0, "cooldown": [0.1, 0.1]}
        brain = EnemyBrain(self.e, self.p, cfg)
        self.p.pos.x, self.e.pos.x = 0, 150
        for n in range(4):                                      # o jogador começa 4 golpes seguidos
            self.p._set("windup")
            self.p.attack = self.atk()
            brain.update(1 / 60, n * 0.5)
            self.p._set("idle")
            brain.update(1 / 60, n * 0.5 + 0.01)
        self.assertGreaterEqual(brain.pressure, 4)
        brain.on_defended("block", 10.0)
        self.assertIsNotNone(brain._riposte_at)
        from entities.fighter import AttackDef
        self.e._set("idle")
        self.e.stamina = 100
        brain._start_attack(AttackDef(windup=0.3, chain=2, stamina_cost=1))
        self.assertEqual(brain._chain_left, 2)

    def test_every_state_draws(self):
        class Cam:
            def to_screen(self, x, y):
                return x + 400, y + 100

        class Assets:
            def image_h(self, rel, h, flip=False):
                return pygame.Surface((120, h), pygame.SRCALPHA)
        surf = pygame.Surface((900, 700), pygame.SRCALPHA)
        font = pygame.font.Font(None, 24)
        from entities.fighter import AttackDef
        self.p.attack = AttackDef(windup=0.3, unblockable=True)
        self.p.grant_counter()
        for state in ("idle", "walk", "windup", "strike", "recover", "hurt", "stunned", "dodge", "block", "dead"):
            self.p.state, self.p.timer = state, 0.05
            self.p.slash_t, self.p.block_flash, self.p.spawn_t, self.p.squash, self.p.flash = 0.1, 1.0, 0.2, 0.5, 0.1
            self.p.draw(surf, Cam(), Assets(), font)
            self.p.update(0.016, (-1e6, 1e6))
        self.assertTrue(self.p.fx_queue is not None)

    def test_particles_new_shapes(self):
        from systems.particles import ParticleSystem
        fx = ParticleSystem(100)
        surf = pygame.Surface((300, 300))
        fx.burst(100, 100, (255, 0, 0), n=10, streak=True, direction=1)
        fx.puff(100, 100, (200, 200, 200), n=4)
        fx.star(100, 100, (255, 255, 0), size=60, life=0.2)
        fx.ring(100, 100, (0, 255, 0), radius=50)
        for _ in range(20):
            fx.update(0.016)
            fx.draw(surf)
        fx.scale = 0
        fx.puff(1, 1, (1, 1, 1))
        fx.star(1, 1, (1, 1, 1))
        self.assertGreaterEqual(len(fx.parts), 0)


class ArenaFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.engine import Game
        from entities.progression import Profile
        cls.game = Game(headless=True)
        cls.game.profile = Profile(character="kozu")

    def setUp(self):
        from scenes.arena import ArenaScene
        self.game.profile.gold = 0
        self.a = ArenaScene(self.game, 3)
        self.a.intro = 99
        self.game.scenes.stack.clear()
        self.game.scenes.push(self.a)
        self.game.scenes.flush()
        random.seed(2)

    def test_perfect_dodge_gives_counter_stun_and_style(self):
        from entities.fighter import AttackDef
        a, p, e = self.a, self.a.player, self.a.enemy
        p.stamina = 80
        p.dodge()
        p.timer = 0.06
        before = p.stamina
        e.pending_hit = AttackDef(windup=0.5, unblockable=True)
        e.pos.x = p.pos.x + 100
        a._resolve(e, p)
        self.assertTrue(p.counter_ready)
        self.assertEqual(e.state, "stunned")
        self.assertGreaterEqual(a.style_total, 2)
        self.assertGreaterEqual(p.stamina, before + 20)       # esquiva perfeita devolve estamina

    def test_parry_opens_counter_and_stuns_enemy(self):
        from entities.fighter import AttackDef
        a, p, e = self.a, self.a.player, self.a.enemy
        p.set_block(True, a.now)
        e.pending_hit = AttackDef(windup=0.5)
        e.pos.x = p.pos.x + 100
        a._resolve(e, p)
        self.assertTrue(p.counter_ready)
        self.assertTrue(e.state == "stunned")

    def test_whiffing_from_far_away_costs_you(self):
        from entities.fighter import AttackDef
        a, p, e = self.a, self.a.player, self.a.enemy
        e.pos.x = p.pos.x + 900
        p.pending_hit = AttackDef(windup=0.1)
        a._resolve(p, e)
        self.assertEqual(p.state, "stunned")                   # errou: fica exposto

    def test_enemy_blocking_recoils_the_spamming_player(self):
        from entities.fighter import AttackDef
        a, p, e = self.a, self.a.player, self.a.enemy
        e.stamina = 100
        e.parry_window = 0.0
        e.set_block(True, a.now - 5)                           # guarda levantada há tempo: sem parry
        p.pending_hit = AttackDef(windup=0.1)
        e.pos.x = p.pos.x + 100
        a._resolve(p, e)
        self.assertEqual(p.state, "stunned")                   # o golpe bate na guarda e o jogador sofre recuo

    def test_style_bonus_gold_on_win(self):
        a = self.a
        a.result = "win"
        a.style_total = 10
        base = a.edef.get("gold", 20)
        self.game.profile.arena_stage = a.stage
        a._finish()
        self.assertGreater(self.game.profile.gold, base)
        self.assertLessEqual(self.game.profile.gold, int(base * 1.5))

    def test_battle_intro_locks_input_and_ends(self):
        from scenes.arena import INTRO_TOTAL, ArenaScene
        g = self.game
        orig = ArenaScene._intro_enabled
        ArenaScene._intro_enabled = lambda self: True
        try:
            a = ArenaScene(g, 2)
            g.scenes.stack.clear()
            g.scenes.push(a)
            g.scenes.flush()
            self.assertTrue(a.in_intro)
            far = abs(a.enemy.pos.x - a.player.pos.x)
            g.input._pressed.add("attack")
            a.update(1 / 60)
            self.assertEqual(a.player.state, "walk")           # entrando, sem aceitar ataque
            self.assertGreater(far, 440)
            t = 0.0
            while a.in_intro and t < 10:
                a.update(1 / 60)
                a.draw(g.screen)
                t += 1 / 60
            self.assertAlmostEqual(t, INTRO_TOTAL, delta=0.2)
            self.assertAlmostEqual(abs(a.enemy.pos.x - a.player.pos.x), 440, delta=2)
            self.assertEqual((a.player.state, a.enemy.state), ("idle", "idle"))
        finally:
            ArenaScene._intro_enabled = orig

    def test_wide_window_menu_and_arena_draw(self):
        from scenes.arena import ArenaScene
        from scenes.menu import MenuScene
        g = self.game
        pygame.display.set_mode((1800, 720))
        try:
            self.assertTrue(g.display.layout())
            g._on_resize()
            self.assertEqual(g.screen.get_size(), (g.display.canvas_w, 720))
            for scene in (MenuScene(g), ArenaScene(g, 1)):
                g.scenes.stack.clear()
                g.scenes.push(scene)
                for _ in range(10):
                    g.scenes.update(1 / 60)
                    g.scenes.draw(g.screen)
            self.assertEqual(g.scenes.current.camera.view.w, g.display.canvas_w)
        finally:
            pygame.display.set_mode((1280, 720))
            g.display.layout()
            g._on_resize()


class AnimatedUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))

    def tearDown(self):
        ui.pointer = (-999.0, -999.0, False, False)

    def test_button_hover_click_glint_and_ripple(self):
        hits = []
        clock = [0.0]
        orig = ui._now

        def fake_now():
            clock[0] += 0.02                      # cada draw = 20 ms
            return clock[0]
        ui._now = fake_now
        self.addCleanup(setattr, ui, "_now", orig)
        b = ui.Button((100, 100, 300, 60), "Ok", lambda: hits.append(1), sub="sub")
        surf = pygame.Surface((600, 400), pygame.SRCALPHA)
        font = pygame.font.Font(None, 30)
        b.draw(surf, font, False, font)
        self.assertFalse(b.hovered())
        ui.pointer = (150.0, 120.0, True, False)
        self.assertTrue(b.hovered())
        for _ in range(12):
            b.draw(surf, font, False, font)
        self.assertGreater(b._k, 0.2)                              # acendeu com o hover
        ui.pointer = (150.0, 120.0, True, True)
        for _ in range(6):
            b.draw(surf, font, False, font)
        self.assertGreater(b._press, 0.1)                          # afundou com o botão apertado
        b.click((150, 120))
        self.assertEqual(hits, [1])
        self.assertIsNotNone(b._ripple)
        self.assertGreaterEqual(b._glint, 0.0)
        for _ in range(40):
            b.draw(surf, font, True, font)
        b.enabled = False
        b.draw(surf, font, False, font)

    def test_menu_focus_follows_mouse_hover(self):
        a, c = ui.Button((0, 0, 100, 40), "a", lambda: None), ui.Button((0, 60, 100, 40), "c", lambda: None)
        m = ui.Menu([a, c])
        im = InputManager(FakeDisplay(), {})
        im.pointer_pos = (50, 80)
        im.moved = True
        m.update(im)
        self.assertEqual(m.focus, 1)
        im.consume_step()
        im.pointer_pos = (50, 10)                                  # sem movimento: o foco não muda
        m.update(im)
        self.assertEqual(m.focus, 1)

    def test_panel_bar_and_title_render(self):
        surf = pygame.Surface((800, 400), pygame.SRCALPHA)
        font = pygame.font.Font(None, 80)
        ui.panel(surf, (20, 20, 400, 200))
        ui.bar(surf, (30, 250, 300, 20), 0.6, (200, 50, 50), ghost=0.9)
        ui.bar(surf, (30, 280, 300, 20), 0.6, (200, 50, 50), ghost=0.9, rtl=True)
        r = ui.text(surf, font, "Título grande", (400, 300), ui.ACCENT, "midtop")
        self.assertGreater(r.width, 100)
        ui.apply_accessibility(colorblind_mode=False, high_contrast_mode=True)
        try:
            ui.panel(surf, (20, 20, 400, 200))
            ui.text(surf, font, "contraste", (10, 10))
        finally:
            ui.apply_accessibility(colorblind_mode=False, high_contrast_mode=False)


if __name__ == "__main__":
    unittest.main()
