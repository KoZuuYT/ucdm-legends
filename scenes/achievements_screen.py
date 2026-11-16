"""Tela de conquistas: grade de cartões com ícone de item, progresso e segredos ("???")."""
import pygame

from core import mcassets as mc
from core import ui
from core.i18n import tr
from core.scene import Scene
from systems import achievements, backdrop

COLS, CELL_W, CELL_H = 3, 396, 92
GAP = 16
TOP, VIEW_H = 130, 540


class AchievementsScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.scroll = 0.0
        self.items = achievements.defs()
        self.scenery = backdrop.Scenery(game, "night", 600)
        self.pos = self._tree(self.items)                 # id -> (linha, coluna): conquistas encadeadas ficam na mesma linha
        rows = 1 + max(r for r, _ in self.pos.values())
        self.max_scroll = max(0.0, rows * CELL_H - VIEW_H)
        self.back = ui.Button((1280 - 250, 40, 210, 52), "Voltar", lambda: self.game.scenes.pop(fade="slide"))

    @staticmethod
    def _tree(items: list[dict]) -> dict:
        """Árvore de avanços: cada conquista sem "parent" abre uma linha; as filhas seguem à direita."""
        kids: dict[str, list[str]] = {}
        for d in items:
            if d.get("parent"):
                kids.setdefault(d["parent"], []).append(d["id"])
        pos, row = {}, 0
        for d in items:
            if d.get("parent"):
                continue
            chain, cur = [d["id"]], d["id"]
            while kids.get(cur):
                cur = kids[cur][0]
                chain.append(cur)
            for col, cid in enumerate(chain[:COLS]):
                pos[cid] = (row, col)
            row += 1
        for d in items:                                  # órfãs (pai desconhecido) ganham uma linha própria
            if d["id"] not in pos:
                pos[d["id"]] = (row, 0)
                row += 1
        return pos

    def _rect(self, cid: str) -> pygame.Rect:
        r, c = self.pos[cid]
        return pygame.Rect(40 + c * (CELL_W + GAP), TOP + r * CELL_H - int(self.scroll), CELL_W, CELL_H - 10)

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if self.t > 0.15 and inp.pressed("back"):
            ui.sfx("back")
            return self.game.scenes.pop(fade="slide")
        if inp.pressed("down"):
            self.scroll += 60
        if inp.pressed("up"):
            self.scroll -= 60
        self.scroll -= inp.wheel * 60
        if inp.pointers:
            self.scroll -= inp.drag_delta.y
        self.scroll = max(0.0, min(self.max_scroll, self.scroll))
        for pos in inp.taps:
            if self.back.rect.collidepoint(pos):
                return self.back.on_click()

    def _icon(self, name: str, k: int = 3):
        return mc.sprite(f"item/{name}.png", k)

    def draw(self, surf: pygame.Surface) -> None:
        a = self.game.assets
        p = self.game.profile
        self.scenery.draw(surf, self.t)
        got = sum(1 for d in self.items if achievements.unlocked(p, d))
        ui.text(surf, a.font(46), f"{tr('Conquistas')}  {got}/{len(self.items)}", (40, 36), ui.ACCENT)
        self.back.draw(surf, a.font(24))
        clip = pygame.Rect(30, TOP, 1220, VIEW_H)
        surf.set_clip(clip)
        for d in self.items:                             # ligações da árvore (atrás dos cartões)
            par = d.get("parent")
            if par and par in self.pos and d["id"] in self.pos:
                a1, b1 = self._rect(par), self._rect(d["id"])
                col = ui.ACCENT if achievements.unlocked(p, next(x for x in self.items if x["id"] == par)) else (80, 82, 100)
                pygame.draw.line(surf, col, (a1.right, a1.centery), (b1.left, b1.centery), 6)
                pygame.draw.polygon(surf, col, [(b1.left - 2, b1.centery), (b1.left - 12, b1.centery - 8), (b1.left - 12, b1.centery + 8)])
        for d in self.items:
            rect = self._rect(d["id"])
            if rect.bottom < TOP or rect.top > TOP + VIEW_H:
                continue
            done = achievements.unlocked(p, d)
            hidden = d.get("secret") and not done
            ui.panel(surf, rect, (30, 34, 50, 235) if done else (22, 24, 34, 215), accent=done)
            icon = self._icon(d["icon"])
            if icon is not None:
                box = pygame.Rect(rect.x + 14, rect.y + 14, 64, 64)
                pygame.draw.rect(surf, (54, 58, 80) if done else (34, 36, 48), box, border_radius=6)
                pygame.draw.rect(surf, ui.ACCENT if done else (70, 72, 90), box, 2, border_radius=6)
                if not done:
                    icon = icon.copy()
                    icon.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
                    icon.fill((50, 52, 68), special_flags=pygame.BLEND_RGB_ADD)
                surf.blit(icon, icon.get_rect(center=box.center))
            name = tr(d["name"]) if not hidden else "???"
            desc = tr(d["desc"]) if not hidden else tr("Conquista secreta")
            name = name if a.font(24).size(name)[0] < CELL_W - 190 else name[:16] + "…"
            ui.text(surf, a.font(24), name, (rect.x + 94, rect.y + 12), ui.ACCENT if done else (200, 202, 215))
            desc = desc if a.font(17, bold=False).size(desc)[0] < CELL_W - 106 else desc[:34] + "…"
            ui.text(surf, a.font(17, bold=False), desc, (rect.x + 94, rect.y + 42), (210, 212, 225) if done else (150, 152, 168))
            cur, need = achievements.progress(p, d)
            if done:
                ui.text(surf, a.font(18), tr("Concluída"), (rect.right - 12, rect.y + 16), ui.GREEN, "topright")
            elif not hidden:
                ui.bar(surf, (rect.x + 94, rect.bottom - 22, 220, 10), cur / need, ui.BLUE)
                ui.text(surf, a.font(15, bold=False), f"{cur}/{need}", (rect.x + 322, rect.bottom - 26))
        surf.set_clip(None)
        if self.max_scroll:
            k = self.scroll / self.max_scroll
            pygame.draw.rect(surf, (80, 80, 100), (1256, TOP, 6, VIEW_H), border_radius=3)
            pygame.draw.rect(surf, ui.ACCENT, (1256, TOP + k * (VIEW_H - 60), 6, 60), border_radius=3)
