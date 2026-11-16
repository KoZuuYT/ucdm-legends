"""Tutorial interativo: o Steve num campo vazio; cada etapa pede uma ação de verdade (mover, atacar, defender, esquivar)."""
import math

import pygame

from core import ui
from core.i18n import tr
from core.input import pretty_key
from core.scene import Scene
from entities import roster
from systems import backdrop

# (ação, quantas vezes, instrução)
STEPS = (
    ("right", 3, "Mova-se para a direita"),
    ("left", 3, "Mova-se para a esquerda"),
    ("attack", 3, "Ataque (o golpe tem preparo, ação e recuperação)"),
    ("block", 2, "Defenda: segure no instante em que o golpe inimigo chegar"),
    ("dodge", 2, "Esquive para sair do alcance do golpe"),
)


class TutorialScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.step = 0
        self.count = 0
        self.x = 640.0
        self.face = 1
        self.anim = ("", 0.0)               # ação recente (para animar o boneco)
        self.done_t = 0.0
        self.scenery = backdrop.Scenery(game, "meadow", 600)

    def enter(self) -> None:
        from core.input import VirtualButton
        W, H = self.game.display.canvas_w, self.game.display.height
        s, m = 100, 18
        self.game.input.set_virtual_buttons([
            VirtualButton("left", pygame.Rect(m, H - s - m, s, s), "<"),
            VirtualButton("right", pygame.Rect(m * 2 + s, H - s - m, s, s), ">"),
            VirtualButton("block", pygame.Rect(W - 3 * (s + m), H - s - m, s, s), "DEF"),
            VirtualButton("dodge", pygame.Rect(W - 2 * (s + m), H - s - m, s, s), "ESQ"),
            VirtualButton("attack", pygame.Rect(W - (s + m), H - s - m, s, s), "ATK"),
            VirtualButton("back", pygame.Rect(W - 72, 8, 60, 60), "X"),
        ])

    def exit(self) -> None:
        self.game.input.set_virtual_buttons([])

    def _key(self, action: str) -> str:
        ks = self.game.input.bindings.get(action, [])
        return pretty_key(ks[0]) if ks else "?"

    def _finish(self) -> None:
        p = self.game.profile
        if p is not None:
            p.counters["tutorial"] = 1
            self.game.save.save(p)
        self.game.feedback.toast(tr("Tutorial concluído!"), (140, 230, 140), 2.5)
        self.game.audio.play("levelup")
        self.game.scenes.pop(fade=True)

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if inp.pressed("back"):
            return self._finish() if self.step >= len(STEPS) else self.game.scenes.pop(fade=True)
        if inp.held("left"):
            self.x -= 260 * dt
            self.face = -1
        if inp.held("right"):
            self.x += 260 * dt
            self.face = 1
        self.x = max(140.0, min(1140.0, self.x))
        a, t0 = self.anim
        if t0 > 0:
            self.anim = (a, t0 - dt)
        if self.step >= len(STEPS):
            self.done_t += dt
            if self.done_t > 0.5 and (inp.pressed("confirm") or inp.pressed("attack") or inp.taps):
                self._finish()
            return
        action, need, _ = STEPS[self.step]
        hit = False
        if action in ("left", "right"):
            hit = inp.pressed(action)
        else:
            hit = inp.pressed(action)
            if hit:
                self.anim = (action, 0.3)
        if hit:
            self.count += 1
            ui.sfx("click")
            if self.count >= need:
                self.count = 0
                self.step += 1
                self.game.audio.play("coin")

    def draw(self, surf: pygame.Surface) -> None:
        a = self.game.assets
        self.scenery.draw(surf, self.t)
        W, H = surf.get_size()
        pygame.draw.rect(surf, (95, 160, 80), (0, 560, W, H - 560))
        ch = roster.character(self.game.profile.character if self.game.profile else "steve")
        img = a.image_h(ch["sprite"], 240, ch.get("faces", -1) != self.face)
        act, t0 = self.anim
        dx = {"attack": 24 * self.face, "dodge": -40 * self.face}.get(act, 0) * (t0 / 0.3 if t0 > 0 else 0)
        surf.blit(img, img.get_rect(midbottom=(self.x + dx, 560 + 4 * math.sin(self.t * 3))))
        if act == "block" and t0 > 0:
            pygame.draw.circle(surf, (120, 180, 255), (int(self.x + 60 * self.face), 450), 60, 6)
        # painel de instrução
        ui.panel(surf, (240, 40, 800, 150))
        ui.text(surf, a.font(24), tr("Tutorial"), (270, 52), ui.ACCENT)
        if self.step < len(STEPS):
            action, need, msg = STEPS[self.step]
            ui.text(surf, a.font(30), f"{tr(msg)}", (270, 92))
            ui.text(surf, a.font(26), f"[{self._key(action)}]  {self.count}/{need}", (270, 136), ui.WHITE)
            ui.bar(surf, (640, 140, 360, 18), (self.step + self.count / need) / len(STEPS), ui.GREEN)
        else:
            ui.text(surf, a.font(32), tr("Pronto! Você já sabe lutar."), (270, 96), ui.GREEN)
            ui.text(surf, a.font(22), tr("Pressione Enter para sair."), (270, 140))
        ui.text(surf, a.font(18, bold=False), tr("Esc: sair do tutorial"), (W // 2, H - 24), (230, 230, 240), "midbottom")
        self.game.input.draw_virtual_buttons(surf, a.font(24))
