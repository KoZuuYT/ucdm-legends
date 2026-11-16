"""Seleção de personagem: grade rolável com TODOS os personagens UCDM.

Demonstra culling de UI: com 160+ personagens, só as linhas visíveis são
desenhadas e só as miniaturas visíveis são geradas (cache LRU no AssetManager)."""
import pygame

from core import ui
from core.scene import Scene
from entities import roster
from entities.progression import Profile

COLS, CELL_W, CELL_H = 6, 145, 170
GRID_X, GRID_Y, GRID_H = 40, 110, 560


class CharacterSelectScene(Scene):
    def __init__(self, game, new_game: bool) -> None:
        super().__init__(game)
        self.new_game = new_game
        self.chars = roster.characters()
        current = game.profile.character if game.profile else game.cfg.get("default_character")
        self.index = next((i for i, c in enumerate(self.chars) if c["id"] == current), 0)
        self.scroll = 0.0
        self.drawn = 0
        rows = (len(self.chars) + COLS - 1) // COLS
        self.max_scroll = max(0, rows * CELL_H - GRID_H)
        self.confirm_btn = ui.Button((1280 - 330, 600, 290, 70), "Escolher", self._confirm)
        self.back_btn = ui.Button((1280 - 330, 30, 290, 56), "Voltar", lambda: self.game.scenes.pop(fade=True))
        self._ensure_visible()

    def _ensure_visible(self) -> None:
        row_y = (self.index // COLS) * CELL_H
        if row_y < self.scroll:
            self.scroll = row_y
        elif row_y + CELL_H > self.scroll + GRID_H:
            self.scroll = row_y + CELL_H - GRID_H

    def _confirm(self) -> None:
        cid = self.chars[self.index]["id"]
        from scenes.hub import HubScene
        if self.new_game:
            self.game.profile = Profile(character=cid)
            self.game.save.save(self.game.profile)
            self.game.scenes.reset(HubScene(self.game))
        else:
            self.game.profile.character = cid
            self.game.save.save(self.game.profile)
            self.game.scenes.pop(fade=True)

    def exit(self) -> None:
        # libera as imagens originais; miniaturas ficam no LRU e expiram sozinhas
        self.game.assets.unload("sprites/characters/")

    def _cell_rect(self, i: int) -> pygame.Rect:
        r, c = divmod(i, COLS)
        return pygame.Rect(GRID_X + c * CELL_W, GRID_Y + r * CELL_H - int(self.scroll), CELL_W - 10, CELL_H - 10)

    def update(self, dt: float) -> None:
        inp = self.game.input
        n = len(self.chars)
        moved = True
        if inp.pressed("right"):
            self.index = (self.index + 1) % n
        elif inp.pressed("left"):
            self.index = (self.index - 1) % n
        elif inp.pressed("down"):
            self.index = min(n - 1, self.index + COLS)
        elif inp.pressed("up"):
            self.index = max(0, self.index - COLS)
        else:
            moved = False
        if moved:
            self._ensure_visible()
        if inp.pressed("confirm"):
            return self._confirm()
        if inp.pressed("back"):
            return self.game.scenes.pop(fade=True)
        self.scroll -= inp.wheel * 60
        if inp.pointers:
            self.scroll -= inp.drag_delta.y
        self.scroll = max(0.0, min(self.max_scroll, self.scroll))
        grid_area = pygame.Rect(GRID_X, GRID_Y, COLS * CELL_W, GRID_H)
        for pos in inp.taps:
            if self.confirm_btn.rect.collidepoint(pos):
                return self._confirm()
            if self.back_btn.rect.collidepoint(pos):
                return self.back_btn.on_click()
            if grid_area.collidepoint(pos):
                first = int(self.scroll // CELL_H) * COLS
                for i in range(first, min(n, first + COLS * (GRID_H // CELL_H + 2))):
                    if self._cell_rect(i).collidepoint(pos):
                        self.index = i

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill((26, 28, 40))
        assets = self.game.assets
        ui.text(surf, assets.font(44), "Escolha seu lutador", (GRID_X, 30), ui.ACCENT)
        clip = pygame.Rect(GRID_X, GRID_Y, COLS * CELL_W, GRID_H)
        surf.set_clip(clip)
        first_row = int(self.scroll // CELL_H)
        last_row = int((self.scroll + GRID_H) // CELL_H)
        small = assets.font(15, bold=False)
        self.drawn = 0
        for i in range(first_row * COLS, min(len(self.chars), (last_row + 1) * COLS)):   # culling
            rect = self._cell_rect(i)
            sel = i == self.index
            pygame.draw.rect(surf, (70, 64, 40) if sel else (44, 46, 62), rect, border_radius=10)
            pygame.draw.rect(surf, ui.ACCENT if sel else (80, 84, 100), rect, 3 if sel else 1, border_radius=10)
            img = assets.image_h(self.chars[i]["sprite"], 110)
            if img.get_width() > rect.width - 10:
                img = assets.image_h(self.chars[i]["sprite"], int(110 * (rect.width - 10) / img.get_width()))
            surf.blit(img, img.get_rect(midbottom=(rect.centerx, rect.bottom - 30)))
            ui.text(surf, small, self.chars[i]["name"][:16], (rect.centerx, rect.bottom - 22), anchor="midtop",
                    shadow=False)
            self.drawn += 1
        surf.set_clip(None)
        # painel de preview
        c = self.chars[self.index]
        big = assets.image_h(c["sprite"], 300)
        if big.get_width() > 290:
            big = assets.image_h(c["sprite"], int(300 * 290 / big.get_width()))
        surf.blit(big, big.get_rect(midbottom=(1280 - 185, 560)))
        ui.text(surf, assets.font(30), c["name"], (1280 - 185, 120), anchor="midtop")
        self.confirm_btn.draw(surf, assets.font(32), True)
        self.back_btn.draw(surf, assets.font(26))
        if self.max_scroll:
            k = self.scroll / self.max_scroll
            pygame.draw.rect(surf, (80, 80, 100), (GRID_X + COLS * CELL_W + 4, GRID_Y, 6, GRID_H), border_radius=3)
            pygame.draw.rect(surf, ui.ACCENT, (GRID_X + COLS * CELL_W + 4, GRID_Y + k * (GRID_H - 60), 6, 60),
                             border_radius=3)

    def debug_info(self) -> str:
        return f"Células desenhadas {self.drawn}/{len(self.chars)}"
