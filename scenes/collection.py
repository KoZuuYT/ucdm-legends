"""Álbum de Lendas: coleção das lendas UCDM (com raridade) e aparências do Steve.

O jogador é sempre o Steve. As lendas do UCDM são os adversários: cada raridade abre quando a escada da
arena chega a um estágio e a primeira vitória sobre uma lenda a adiciona ao álbum. Aparências do Steve
desbloqueiam por metas (vitórias, estágio, tamanho da coleção).

Culling de UI: só as linhas visíveis da grade são desenhadas (160+ cartas)."""
import math

import pygame

from core import ui
from core.i18n import tr
from core.scene import Scene
from entities import roster

COLS, CELL_W, CELL_H = 6, 145, 170
GRID_X, GRID_Y, GRID_H = 40, 150, 520
MODES = ("legends", "skins")


class CollectionScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.mode = "legends"
        self.filter = 0                    # 0 = todas; 1.. = raridade
        self.query = ""                    # busca por texto (nome, sem acento)
        self.mark: str | None = None       # carta marcada para comparar (tecla de ataque)
        self.typing = False
        self.index = 0
        self.scroll = 0.0
        self.t = 0.0
        self.drawn = 0
        self.toast = ("", 0.0)
        self._sil: dict[tuple, pygame.Surface] = {}
        self._rebuild()
        self.act_btn = ui.Button((1280 - 330, 600, 290, 70), "Desafiar", self._act)
        self.back_btn = ui.Button((1280 - 330, 30, 290, 56), "Voltar", lambda: self.game.scenes.pop(fade="slide"))
        self.mode_btn = ui.Button((GRID_X, 84, 260, 48), "Aparências", self._toggle_mode)
        self.filter_btn = ui.Button((GRID_X + 270, 84, 260, 48), "Raridade: todas", self._cycle_filter)
        self.search_btn = ui.Button((GRID_X + 540, 84, 260, 48), "Buscar", self._toggle_search)

    # --- dados --------------------------------------------------------------------------
    @property
    def profile(self):
        return self.game.profile

    def _rebuild(self) -> None:
        if self.mode == "skins":
            self.items = roster.skins()
        else:
            items = roster.characters()
            order = roster.rarity_order()
            if self.filter:
                want = order[self.filter - 1]
                items = [c for c in items if c.get("rarity", "comum") == want]
            if self.query:
                from scenes.options import _norm
                q = _norm(self.query)
                items = [c for c in items if q in _norm(c["name"])]
            # ordem: raridade (mais rara primeiro), depois nome
            self.items = sorted(items, key=lambda c: (-order.index(c.get("rarity", "comum")), c["name"].lower()))
        self.index = min(self.index, max(0, len(self.items) - 1))
        rows = (len(self.items) + COLS - 1) // COLS
        self.max_scroll = max(0, rows * CELL_H - GRID_H)
        self._ensure_visible()

    def _toggle_mode(self) -> None:
        self.mode = "skins" if self.mode == "legends" else "legends"
        self.index, self.scroll = 0, 0.0
        if self.mode == "skins":
            cur = self.profile.character
            self.items = roster.skins()
            self.index = next((i for i, s in enumerate(self.items) if s["id"] == cur), 0)
        self.mode_btn.label = "Lendas" if self.mode == "skins" else "Aparências"
        self._rebuild()
        ui.sfx("select")

    def _toggle_search(self) -> None:
        if self.typing:
            return self._stop_typing()
        self.typing = True
        self.game.input.capture = True
        self.game.input.captured = None
        pygame.key.start_text_input()
        self.search_btn.label = "Buscar: _"

    def _stop_typing(self) -> None:
        if self.typing:
            self.typing = False
            self.game.input.capture = False
            pygame.key.stop_text_input()
        self.search_btn.label = f"{tr('Buscar')}: {self.query}" if self.query else "Buscar"

    def _type(self, inp) -> None:
        old = self.query
        for ch in inp.text_input:
            if ch.isprintable() and len(self.query) < 16:
                self.query += ch
        key, inp.captured = inp.captured, None
        if key == "backspace":
            self.query = self.query[:-1]
        elif key in ("return", "escape", "enter"):
            return self._stop_typing()
        self.search_btn.label = f"{tr('Buscar')}: {self.query}_"
        if self.query != old:
            self.index = 0
            self.scroll = 0.0
            self._rebuild()

    def _cycle_filter(self) -> None:
        if self.mode != "legends":
            return
        self.filter = (self.filter + 1) % (len(roster.rarity_order()) + 1)
        label = "todas" if not self.filter else roster.rarity_info(roster.rarity_order()[self.filter - 1])["label"]
        self.filter_btn.label = f"{tr('Raridade')}: {tr(label)}"
        self.index, self.scroll = 0, 0.0
        self._rebuild()

    def _ensure_visible(self) -> None:
        row_y = (self.index // COLS) * CELL_H
        if row_y < self.scroll:
            self.scroll = row_y
        elif row_y + CELL_H > self.scroll + GRID_H:
            self.scroll = row_y + CELL_H - GRID_H

    # --- estado de um item -----------------------------------------------------------------
    def _known(self, item: dict) -> bool:
        if self.mode == "skins":
            return roster.unlocked_skin(self.profile, item)
        return item["id"] in self.profile.collection

    def _tier_ok(self, item: dict) -> bool:
        return roster.tier_unlocked(self.profile, item.get("rarity", "comum"))

    def _act(self) -> None:
        if not self.items:
            return
        item = self.items[self.index]
        p = self.profile
        if self.mode == "skins":
            if not roster.unlocked_skin(p, item):
                self.toast = (roster.skin_requirement(item), 2.5)
                return ui.sfx("error")
            p.character = item["id"]
            self.game.save.save(p)
            self.toast = (f"Aparência: {item['name']}", 2.0)
            return ui.sfx("select")
        if not self._tier_ok(item):
            need = roster.rarity_info(item.get("rarity", "comum"))["unlock_stage"]
            self.toast = (f"Requer a luta {need + 1} da arena" if need < len(roster.enemies())
                          else "Requer vencer o chefe da arena", 2.5)
            return ui.sfx("error")
        from scenes.arena import ArenaScene
        self.game.scenes.push(ArenaScene(self.game, 0, challenger=item["id"]), fade="diag")

    def resume(self) -> None:
        self._rebuild()

    def exit(self) -> None:
        self._stop_typing()
        self.game.assets.unload("sprites/characters/")
        self.game.assets.unload("sprites/thumbs/")

    # --- ciclo ------------------------------------------------------------------------------
    def _cell_rect(self, i: int) -> pygame.Rect:
        r, c = divmod(i, COLS)
        return pygame.Rect(GRID_X + c * CELL_W, GRID_Y + r * CELL_H - int(self.scroll), CELL_W - 10, CELL_H - 10)

    def update(self, dt: float) -> None:
        self.t += dt
        self.toast = (self.toast[0], self.toast[1] - dt)
        inp = self.game.input
        if self.typing:
            self._type(inp)
            return
        n = len(self.items)
        moved = True
        if n and inp.pressed("right"):
            self.index = (self.index + 1) % n
        elif n and inp.pressed("left"):
            self.index = (self.index - 1) % n
        elif n and inp.pressed("down"):
            self.index = min(n - 1, self.index + COLS)
        elif n and inp.pressed("up"):
            self.index = max(0, self.index - COLS)
        else:
            moved = False
        if moved:
            self._ensure_visible()
        if inp.pressed("confirm"):
            return self._act()
        if inp.pressed("back"):
            return self.game.scenes.pop(fade="slide")
        if inp.pressed("attack") and self.mode == "legends" and n:
            cid = self.items[self.index]["id"]
            self.mark = None if self.mark == cid else cid
            ui.sfx("click")
        if inp.pressed("dodge"):
            self._toggle_mode()
        if inp.pressed("block"):
            self._cycle_filter()
        self.scroll -= inp.wheel * 60
        if inp.pointers:
            self.scroll -= inp.drag_delta.y
        self.scroll = max(0.0, min(self.max_scroll, self.scroll))
        grid_area = pygame.Rect(GRID_X, GRID_Y, COLS * CELL_W, GRID_H)
        for pos in inp.taps:
            for b in (self.act_btn, self.back_btn, self.mode_btn, self.filter_btn, self.search_btn):
                if b.rect.collidepoint(pos):
                    return b.on_click()
            if grid_area.collidepoint(pos):
                first = int(self.scroll // CELL_H) * COLS
                for i in range(first, min(n, first + COLS * (GRID_H // CELL_H + 2))):
                    if self._cell_rect(i).collidepoint(pos):
                        self.index = i

    def _silhouette(self, sprite: str, h: int) -> pygame.Surface:
        key = (sprite, h)
        s = self._sil.get(key)
        if s is None:
            s = self.game.assets.image_h(sprite, h).copy()
            s.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
            s.fill((26, 28, 44), special_flags=pygame.BLEND_RGB_ADD)
            if len(self._sil) > 240:
                self._sil.clear()
            self._sil[key] = s
        return s

    def _color(self, item: dict) -> tuple:
        if self.mode == "skins":
            return ui.ACCENT if self._known(item) else (110, 112, 130)
        return roster.rarity_color(item.get("rarity", "comum"))

    def _portrait(self, item: dict, h: int, known: bool) -> pygame.Surface:
        a = self.game.assets
        path = item["sprite"] if self.mode == "skins" else a.thumb_path(item)
        return a.image_h(path, h) if known else self._silhouette(path, h)

    def draw(self, surf: pygame.Surface) -> None:
        ui.backdrop(surf, self.t, animate=not self.game.feedback.reduce_motion)
        a = self.game.assets
        p = self.profile
        total = len(roster.characters())
        if self.mode == "skins":
            got = sum(1 for s in roster.skins() if roster.unlocked_skin(p, s))
            ui.text(surf, a.font(40), f"{tr('Aparências do Steve')}  {got}/{len(roster.skins())}", (GRID_X, 24), ui.ACCENT)
        else:
            ui.text(surf, a.font(40), f"{tr('Álbum de Lendas')}  {len(p.collection)}/{total}", (GRID_X, 24), ui.ACCENT)
        self.mode_btn.draw(surf, a.font(22))
        self.filter_btn.draw(surf, a.font(22), self.mode == "legends")
        self.search_btn.draw(surf, a.font(22), self.mode == "legends")
        clip = pygame.Rect(GRID_X, GRID_Y, COLS * CELL_W, GRID_H)
        surf.set_clip(clip)
        first_row = int(self.scroll // CELL_H)
        last_row = int((self.scroll + GRID_H) // CELL_H)
        small = a.font(15, bold=False)
        reduce = self.game.feedback.reduce_motion or self.game.low_perf
        self.drawn = 0
        for i in range(first_row * COLS, min(len(self.items), (last_row + 1) * COLS)):     # culling
            rect = self._cell_rect(i)
            item = self.items[i]
            sel = i == self.index
            known = self._known(item)
            col = self._color(item)
            if sel:
                pulse = 0.5 + 0.5 * math.sin(self.t * 4) if not reduce else 1.0
                glow = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*col, int(40 + 50 * pulse)), glow.get_rect(), border_radius=14)
                surf.blit(glow, glow.get_rect(center=rect.center))
            pygame.draw.rect(surf, tuple(int(c * 0.22) + 24 for c in col) if sel else (40, 42, 58), rect, border_radius=8)
            pygame.draw.rect(surf, col if (sel or known) else (70, 72, 90), rect, 3 if sel else 2, border_radius=8)
            size = 110
            if sel and not reduce:
                size = int(110 * (1.03 + 0.03 * math.sin(self.t * 3)))
            img = self._portrait(item, size, known)
            surf.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom - 30)))
            name = item["name"][:16] if known or self.mode == "skins" else "???"
            ui.text(surf, small, name, (rect.centerx, rect.bottom - 22), anchor="midtop", shadow=False)
            if self.mode == "legends":
                pygame.draw.rect(surf, col, (rect.x + 6, rect.y + 6, 10, 10), border_radius=2)   # selo de raridade
            elif not known:
                ui.text(surf, a.font(22), "X", (rect.right - 10, rect.y + 4), (200, 90, 90), "topright")
            self.drawn += 1
        surf.set_clip(None)
        self._draw_side(surf)
        if self.mark and self.items and self.mode == "legends" and self.items[self.index]["id"] != self.mark:
            self._draw_compare(surf, self.items[self.index])
        self.back_btn.draw(surf, a.font(26))
        if self.max_scroll:
            k = self.scroll / self.max_scroll
            pygame.draw.rect(surf, (80, 80, 100), (GRID_X + COLS * CELL_W + 4, GRID_Y, 6, GRID_H), border_radius=3)
            pygame.draw.rect(surf, ui.ACCENT, (GRID_X + COLS * CELL_W + 4, GRID_Y + k * (GRID_H - 60), 6, 60), border_radius=3)
        ui.text(surf, a.font(16, bold=False), "Esquiva: Lendas/Aparências   Defesa: raridade   Ataque: marcar p/ comparar   Enter: escolher",
                (GRID_X, 700), (170, 172, 190), "midleft")
        if self.toast[1] > 0:
            ui.text(surf, a.font(26), self.toast[0], (640, 690), ui.ACCENT, "center")

    def _draw_compare(self, surf: pygame.Surface, item: dict) -> None:
        """Comparação lado a lado (vida, dano, defesa) entre a carta marcada e a selecionada."""
        a = self.game.assets
        other = roster.character(self.mark)
        ea, eb = roster.challenge_edef(self.mark), roster.challenge_edef(item["id"])
        base_x, y = 1280 - 330, 180
        box = pygame.Surface((320, 102), pygame.SRCALPHA)
        box.fill((0, 0, 0, 170))
        surf.blit(box, (base_x - 8, y - 6))
        ui.text(surf, a.font(16), f"{tr('Comparar')}: {other['name'][:12]} -> {item['name'][:12]}", (base_x, y), ui.ACCENT)
        for k, (key, label) in enumerate((("hp", "Vida"), ("damage", "Dano"), ("armor", "Armadura"))):
            va, vb = ea.get(key, 0), eb.get(key, 0)
            diff = round(vb - va, 2)
            col = ui.RED if diff > 0 else ui.GREEN if diff < 0 else (190, 190, 200)     # mais forte = mais perigoso
            ui.text(surf, a.font(16, bold=False), f"{tr(label)}: {va} -> {vb}  ({'+' if diff > 0 else ''}{diff})", (base_x, y + 24 + k * 22), col)

    def _draw_side(self, surf: pygame.Surface) -> None:
        a = self.game.assets
        if not self.items:
            return
        item = self.items[self.index]
        p = self.profile
        known = self._known(item)
        col = self._color(item)
        cx = 1280 - 185
        big = self._portrait(item, 300, known)
        if big.get_width() > 290:
            big = self._portrait(item, int(300 * 290 / big.get_width()), known)
        surf.blit(big, big.get_rect(midbottom=(cx, 520)))
        name = item["name"] if known or self.mode == "skins" else "???"
        ui.text(surf, a.font(30), name, (cx, 100), anchor="midtop")
        if self.mode == "skins":
            if known:
                msg, c = ("Em uso" if p.character == item["id"] else "Desbloqueada"), ui.GREEN
            else:
                msg, c = roster.skin_requirement(item), ui.RED
            ui.text(surf, a.font(20, bold=False), msg, (cx, 540), c, "midtop")
            self.act_btn.label = "Usar"
            self.act_btn.draw(surf, a.font(32), known and p.character != item["id"])
            return
        r = item.get("rarity", "comum")
        info = roster.rarity_info(r)
        ui.text(surf, a.font(24), info["label"].upper(), (cx, 138), col, "midtop")
        wins = p.collection.get(item["id"], 0)
        ui.text(surf, a.font(20, bold=False), f"{tr('Derrotado')}: {wins}x" if wins else "Ainda não derrotado",
                (cx, 540), ui.GREEN if wins else (190, 192, 205), "midtop")
        ok = self._tier_ok(item)
        if not ok:
            need = info["unlock_stage"]
            txt = f"Abre na luta {need + 1} da arena" if need < len(roster.enemies()) else "Abre ao vencer o chefe"
            ui.text(surf, a.font(18, bold=False), txt, (cx, 566), ui.RED, "midtop")
        self.act_btn.label = "Desafiar"
        self.act_btn.draw(surf, a.font(32), ok)

    def debug_info(self) -> str:
        return f"Células desenhadas {self.drawn}/{len(self.items)}"
