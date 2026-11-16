"""Seletor de saves (3 slots): jogar, novo jogo, renomear, copiar, exportar, importar e apagar.

Nada é destrutivo sem confirmação: apagar exige segurar o botão e copiar sobre um slot usado pergunta antes.
"""
import time

import pygame

from core import paths, ui
from core.scene import Scene
from entities import roster
from entities.progression import Profile
from scenes.dialogs import ConfirmDialog, TextPrompt
from systems.save import SaveManager
from systems.tween import ease_out_back


def fmt_time(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60:02d}min" if m >= 60 else f"{m}min"


def slot_label(i: int, s: dict | None) -> tuple[str, str]:
    """(título, subtítulo) do cartão de um slot."""
    if s is None:
        return f"Slot {i + 1}: vazio", "Novo jogo"
    try:
        who = roster.character(s["character"])["name"]
    except (KeyError, StopIteration, TypeError):
        who = s["character"]
    title = f"Slot {i + 1}: {s['name'] or who}" + (f"  ({who})" if s["name"] else "")
    when = time.strftime("%d/%m %H:%M", time.localtime(s["mtime"])) if s["mtime"] else "-"
    sub = f"Nv {s['level']}  ·  {s['wins']} vitórias  ·  {fmt_time(s['playtime'])}  ·  {when}"
    if s["from_backup"]:
        sub = "Recuperado do backup  ·  " + sub
    return title, sub


class SaveSelectScene(Scene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self._build()

    def _managers(self) -> list[SaveManager]:
        return [SaveManager(s) for s in paths.SAVE_SLOTS]

    def _build(self) -> None:
        focus = self.menu.focus if hasattr(self, "menu") else 0
        W = self.game.display.width
        self.sums = [m.summary() for m in self._managers()]
        buttons = []
        for i, s in enumerate(self.sums):
            title, sub = slot_label(i, s)
            buttons.append(ui.Button((W // 2 - 460, 150 + i * 150, 920, 130), title, lambda i=i: self._open(i), sub=sub))
        buttons.append(ui.Button((W // 2 - 140, 620, 280, 56), "Voltar", self._back))
        self.menu = ui.Menu(buttons)
        self.menu.focus = min(focus, len(buttons) - 1)

    def resume(self) -> None:
        self._build()

    def _back(self) -> None:
        self.game.scenes.pop(fade="slide")

    def _open(self, i: int) -> None:
        self.game.scenes.push(SlotMenu(self.game, i, self.sums[i]))

    def update(self, dt: float) -> None:
        self.t += dt
        if self.game.input.pressed("back"):
            ui.sfx("back")
            return self._back()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        ui.backdrop(surf, self.t, animate=not self.game.feedback.reduce_motion)
        ui.text(surf, a.font(54), "Seus saves", (W // 2, 50), ui.ACCENT, "midtop")
        for i, b in enumerate(self.menu.buttons[:3]):          # cartões entram em sequência
            k = ease_out_back(min(1.0, max(0.0, (self.t - i * 0.07) / 0.3)))
            b.rect.x = W // 2 - 460 + int((1 - min(1.0, k)) * 80)
            s = self.sums[i]
            if s is not None:   # miniatura do personagem do slot
                try:
                    img = a.image_h(a.thumb_path(roster.character(s["character"])), 100)
                    surf.blit(img, img.get_rect(midright=(b.rect.right - 24, b.rect.centery)))
                except (KeyError, StopIteration):
                    pass
        self.menu.draw(surf, a.font(32), a.font(20, bold=False))


class SlotMenu(Scene):
    """Ações de um slot (modal)."""
    transparent = True
    dim_alpha = 160
    GRACE = 0.2

    def __init__(self, game, index: int, summary: dict | None) -> None:
        super().__init__(game)
        self.index, self.sum = index, summary
        self.slot = paths.SAVE_SLOTS[index]
        self.mgr = SaveManager(self.slot)
        self.t = 0.0
        W, H = game.display.width, game.display.height
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 160))
        items: list[tuple[str, object, bool]] = []
        if summary is None:
            exports = SaveManager.list_exports()
            items = [("Novo jogo", self._new, True),
                     ("Importar" + (f": {exports[0].name[:24]}" if exports else " (sem arquivos)"), self._import,
                      bool(exports))]
        else:
            items = [("Jogar", self._play, True), ("Renomear treinador", self._rename, True)]
            for j, other in enumerate(paths.SAVE_SLOTS):
                if j != index:
                    items.append((f"Copiar para o Slot {j + 1}", lambda o=other: self._copy(o), True))
            items += [("Exportar (.ucdmsave)", self._export, True), ("Apagar slot", self._delete, True)]
        items.append(("Voltar", self._close, True))
        h = 100 + len(items) * 62
        self.panel = pygame.Rect(0, 0, 520, h)
        self.panel.center = (W // 2, H // 2)
        self.menu = ui.Menu([ui.Button((self.panel.x + 40, self.panel.y + 84 + i * 62, 440, 52), lab, fn, enabled=en)
                             for i, (lab, fn, en) in enumerate(items)])

    def _close(self) -> None:
        self.game.scenes.pop()

    # --- ações ------------------------------------------------------------------------
    def _play(self) -> None:
        g = self.game
        g.use_slot(self.slot)
        data = g.save.load_raw()
        if data is None:
            g.feedback.toast("Não foi possível ler este save.", ui.RED)
            return self._close()
        g.profile = Profile.from_dict(data)
        if data.get("_from_backup"):
            g.feedback.toast("Save principal corrompido: carregado do backup.", ui.ACCENT, 4.0)
        from scenes.hub import HubScene
        g.scenes.reset(HubScene(g), fade="iris")

    def _new(self) -> None:
        from scenes.hub import HubScene
        g = self.game
        g.use_slot(self.slot)
        g.profile = Profile()                    # o jogador é sempre o Steve
        g.save.save(g.profile)
        g.scenes.reset(HubScene(g), fade="iris")

    def _rename(self) -> None:
        def ok(name: str) -> None:
            data = self.mgr.load_raw() or {}
            data["name"] = name[:16]
            self.mgr.write_dict(data)
            self.game.feedback.toast("Nome atualizado.", ui.GREEN)
            self.game.scenes.pop()          # fecha este menu; o seletor se atualiza em resume()
        self.game.scenes.push(TextPrompt(self.game, "Nome do treinador", self.sum["name"] if self.sum else "", ok))

    def _copy(self, other_slot: str) -> None:
        other = SaveManager(other_slot)

        def do() -> None:
            if self.mgr.copy_to(other):
                self.game.feedback.toast(f"Copiado para {other_slot.replace('slot', 'o Slot ')}.", ui.GREEN)
            else:
                self.game.feedback.toast("Falha ao copiar.", ui.RED)
            self.game.scenes.pop()
        if other.exists():
            self.game.scenes.push(ConfirmDialog(
                self.game, "Sobrescrever?", f"O {other_slot.replace('slot', 'Slot ')} já tem um save.\nEle será substituído.",
                on_yes=do, yes_label="Sobrescrever", danger=True))
        else:
            do()

    def _export(self) -> None:
        out = self.mgr.export()
        if out:
            self.game.feedback.toast(f"Exportado: {out.name}", ui.GREEN, 4.0)
        else:
            self.game.feedback.toast("Nada para exportar.", ui.RED)

    def _import(self) -> None:
        files = SaveManager.list_exports()
        if files and self.mgr.import_file(files[0]):
            self.game.feedback.toast(f"Importado: {files[0].name}", ui.GREEN, 4.0)
            self.game.scenes.pop()
        else:
            self.game.feedback.toast("Arquivo inválido.", ui.RED)

    def _delete(self) -> None:
        def do() -> None:
            self.mgr.delete()
            if self.game.slot == self.slot:
                self.game.profile = None
            self.game.feedback.toast("Slot apagado.", ui.ACCENT)
            self.game.scenes.pop()
        self.game.scenes.push(ConfirmDialog(
            self.game, "Apagar slot?", f"Todo o progresso do Slot {self.index + 1} será perdido.\n"
            "Isso não pode ser desfeito. (Exporte antes, se quiser guardar.)",
            on_yes=do, yes_label="Apagar", hold=1.5, danger=True))

    # --- ciclo ------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.t += dt
        if self.t < self.GRACE:
            return
        if self.game.input.pressed("back"):
            ui.sfx("back")
            return self._close()
        self.menu.update(self.game.input)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        k = min(1.0, ease_out_back(min(1.0, self.t / 0.25)))
        off = int((1 - k) * 40)
        a = self.game.assets
        ui.panel(surf, self.panel.move(0, off), (20, 22, 32, 240))
        title, _ = slot_label(self.index, self.sum)
        ui.text(surf, a.font(34), title[:34], (self.panel.centerx, self.panel.top + 24 + off), ui.ACCENT, "midtop")
        for i, b in enumerate(self.menu.buttons):
            b.rect.y = self.panel.y + 84 + i * 62 + off
        self.menu.draw(surf, a.font(26))
