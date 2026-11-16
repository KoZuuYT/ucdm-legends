"""Ajuda: tutorial da primeira vez (pulável), glossário, controles atuais (com rebind) e créditos."""
import pygame

from core import ui
from core.i18n import tr
from core.scene import Scene
from systems.tween import ease_out_back


def _keys(game, action: str) -> str:
    ks = game.input.bindings.get(action, [])
    return " / ".join(k.upper() for k in ks) if ks else "—"


class _Panel(Scene):
    transparent = True
    dim_alpha = 170
    GRACE = 0.2

    def __init__(self, game, size=(960, 560)) -> None:
        super().__init__(game)
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, *size)
        self.panel.center = (W // 2, H // 2)
        self.t = 0.0
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 170))

    def _off(self) -> int:
        return int((1 - min(1.0, ease_out_back(min(1.0, self.t / 0.28)))) * 50)


class HelpOverlay(_Panel):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.page = 0
        self.pages = [self._controls, self._combat, self._progress]
        self.titles = ["Controles", "Combate", "Treino e progresso"]

    # cada página devolve (linhas de texto)
    def _controls(self) -> list[str]:
        g = self.game
        return [
            f"Mover:  {_keys(g, 'left')}  /  {_keys(g, 'right')}",
            f"Atacar:  {_keys(g, 'attack')}      Defender (segure):  {_keys(g, 'block')}",
            f"Esquivar:  {_keys(g, 'dodge')}      Confirmar:  {_keys(g, 'confirm')}",
            "Esc: voltar / pausar      F11: tela cheia      F3: FPS",
            "",
            "Nos treinos, use as setas conforme a seta que aparecer.",
            "Dá para remapear as teclas em Opções > Controles.",
            "Controle: A confirma/ataca · B esquiva · X defende · Start volta",
        ]

    def _combat(self) -> list[str]:
        return [
            "PARRY: defenda no instante exato do golpe. O inimigo fica atordoado!",
            "ESQUIVA PERFEITA: esquive no último instante. Ela e o PARRY abrem um CONTRA-ATAQUE (crítico garantido).",
            "Vermelho (!!): imbloqueável, esquive. Laranja: quebra a guarda, aparar ou esquive.",
            "Inimigos têm ARMADURA: golpes comuns fazem pouco dano. Parry, esquiva perfeita e contra-ataque a quebram.",
            "Atacar sem parar causa FADIGA (menos dano) e gasta estamina. O inimigo aprende e se defende.",
            "Segurar a guarda gasta estamina. Esquivar no tempo certo devolve estamina e rende bônus de ouro.",
        ]

    def _progress(self) -> list[str]:
        return [
            "Cada treino sobe um atributo:",
            "   Golpe > Força   ·   Escudo > Defesa   ·   Esquiva > Agilidade   ·   Mira > Foco",
            "Ouro das lutas e treinos melhora a arma (mais dano).",
            "A Arena tem 8 desafiantes em sequência, até o chefe.",
            "O jogo salva sozinho. Veja suas estatísticas no Campo de Treino.",
        ]

    def _close(self) -> None:
        self.game.scenes.pop()

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t < self.GRACE:
            return
        inp = self.game.input
        if inp.pressed("back"):
            ui.sfx("back")
            return self._close()
        if inp.pressed("right") or inp.pressed("confirm"):
            if self.page == len(self.pages) - 1:
                ui.sfx("confirm")
                return self._close()
            self.page += 1
            ui.sfx("click")
        elif inp.pressed("left") and self.page > 0:
            self.page -= 1
            ui.sfx("click")
        for pos in inp.taps:
            if pos[0] > self.panel.centerx:
                if self.page == len(self.pages) - 1:
                    return self._close()
                self.page += 1
            elif self.page > 0:
                self.page -= 1

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        a = self.game.assets
        pr = self.panel.move(0, self._off())
        ui.panel(surf, pr, (20, 22, 32, 245))
        ui.text(surf, a.font(24, bold=False), "TUTORIAL", (pr.x + 30, pr.y + 20), (170, 170, 180))
        ui.text(surf, a.font(48), self.titles[self.page], (pr.centerx, pr.y + 50), ui.ACCENT, "midtop")
        y = pr.y + 130
        font = a.font(24, bold=False)
        for line in self.pages[self.page]():
            if not line:
                y += 16
                continue
            for j, part in enumerate(ui.wrap_text(font, tr(line), pr.w - 110)):
                ui.text(surf, font, part, (pr.x + 50 + (28 if j else 0), y))
                y += 30
            y += 12
        for i in range(len(self.pages)):
            pygame.draw.circle(surf, ui.ACCENT if i == self.page else (90, 90, 110), (pr.centerx + (i - 1) * 26, pr.bottom - 64), 7)
        last = self.page == len(self.pages) - 1
        ui.text(surf, a.font(20, bold=False), "<  anterior" if self.page else "", (pr.x + 40, pr.bottom - 40), (200, 200, 210))
        ui.text(surf, a.font(20, bold=False), "Fechar  (Enter)" if last else "próxima  >", (pr.right - 40, pr.bottom - 40),
                (200, 200, 210), "topright")


class CreditsOverlay(_Panel):
    def __init__(self, game) -> None:
        super().__init__(game, (860, 560))

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t > self.GRACE and (self.game.input.pressed("back") or self.game.input.pressed("confirm") or self.game.input.taps):
            ui.sfx("back")
            self.game.scenes.pop()

    def draw(self, surf: pygame.Surface) -> None:
        from scenes.menu import _read_version
        surf.blit(self._dim, (0, 0))
        a = self.game.assets
        pr = self.panel.move(0, self._off())
        ui.panel(surf, pr, (20, 22, 32, 245))
        ui.text(surf, a.font(52), self.game.cfg["title"], (pr.centerx, pr.y + 28), ui.ACCENT, "midtop")
        lines = [f"Versão {_read_version()}", "", "Personagens e universo UCDM: criados pelos amigos do UCDM.",
                 "Jogo feito com Python e pygame-ce.", "Sons e músicas gerados por código (tools/make_sfx.py).",
                 "Gráficos de Minecraft © Mojang Studios / Microsoft.",
                 "Projeto de fãs, gratuito e sem fins lucrativos; não afiliado à Mojang nem à Microsoft.",
                 "", "github.com/KoZuuYT/ucdm-legends"]
        for i, line in enumerate(lines):
            for j, part in enumerate(ui.wrap_text(a.font(22, bold=False), tr(line), pr.w - 80)):
                ui.text(surf, a.font(22, bold=False), part, (pr.centerx, pr.y + 112 + i * 38 + j * 24), anchor="midtop")
