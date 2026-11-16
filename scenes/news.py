"""Novidades da versão: aparece uma vez no menu depois de uma atualização."""
import pygame

from core import ui
from scenes.help import _Panel


def wrap_text(font, text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.size(trial)[0] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def split_sentences(notes: str) -> list[str]:
    """Quebra as notas em frases curtas para virar uma lista legível."""
    parts = [p.strip() for p in notes.replace("\n", " ").split(". ") if p.strip()]
    return [p if p.endswith(".") else p + "." for p in parts]


class NewsOverlay(_Panel):
    def __init__(self, game, version: str, notes: str) -> None:
        super().__init__(game, (900, 520))
        self.version, self.notes = version, notes

    def update(self, dt: float) -> None:
        self.t += dt
        inp = self.game.input
        if self.t > self.GRACE and (inp.pressed("back") or inp.pressed("confirm") or inp.taps):
            ui.sfx("confirm")
            self.game.scenes.pop()

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        a = self.game.assets
        pr = self.panel.move(0, self._off())
        ui.panel(surf, pr, (20, 22, 32, 245))
        ui.text(surf, a.font(44), f"Novidades da v{self.version}", (pr.centerx, pr.y + 24), ui.ACCENT, "midtop")
        font = a.font(22, bold=False)
        y = pr.y + 100
        for sentence in split_sentences(self.notes):
            for j, line in enumerate(wrap_text(font, sentence, pr.w - 110)):
                if y > pr.bottom - 70:
                    break
                ui.text(surf, font, ("•  " if j == 0 else "    ") + line, (pr.x + 40, y))
                y += 28
            y += 8
        ui.text(surf, a.font(18, bold=False), "Enter para continuar", (pr.centerx, pr.bottom - 36), (190, 190, 200), "midtop")
