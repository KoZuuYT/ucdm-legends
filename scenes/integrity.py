"""Verificação de arquivos do jogo e reparo (reinstala a versão atual sem tocar em saves/configurações)."""
import pygame

from core import ui
from core.scene import Scene
from network import integrity
from network import release_tools as rt
from network.updater import UpdateInfo, UpdateTask, can_self_update, install_dir, local_version
from scenes.dialogs import ConfirmDialog
from systems.tween import ease_out_back


class IntegrityOverlay(Scene):
    transparent = True
    GRACE = 0.2

    def __init__(self, game) -> None:
        super().__init__(game)
        W, H = game.display.width, game.display.height
        self.panel = pygame.Rect(0, 0, 760, 420)
        self.panel.center = (W // 2, H // 2)
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 170))
        self.t = 0.0
        self.task = integrity.IntegrityTask(install_dir())
        self.menu: ui.Menu | None = None
        self._built = False

    def enter(self) -> None:
        self.task.start()

    def _build_menu(self) -> None:
        r = self.task.result or {}
        x, y, w = self.panel.x + 60, self.panel.bottom - 90, 300
        buttons = []
        if r.get("state") == "problems":
            buttons.append(ui.Button((x, y, w, 56), "Reparar", self._repair, enabled=can_self_update()))
            buttons.append(ui.Button((x + w + 40, y, w, 56), "Fechar", self._close))
        else:
            buttons.append(ui.Button((self.panel.centerx - 130, y, 260, 56), "Fechar", self._close))
        self.menu = ui.Menu(buttons)
        self.menu.focus = 0 if r.get("state") == "problems" and can_self_update() else len(buttons) - 1
        self._built = True

    def _close(self) -> None:
        self.game.scenes.pop()

    def _repair(self) -> None:
        self.game.scenes.push(ConfirmDialog(
            self.game, "Reparar o jogo?", "Vamos baixar a versão atual de novo e trocar os arquivos.\n"
            "Saves e configurações não são alterados. O jogo reabre sozinho.",
            on_yes=lambda: self.game.scenes.replace(RepairScene(self.game), fade=True), yes_label="Reparar"))

    def update(self, dt: float) -> None:
        self.t += dt
        if (self.task.result is not None or self.task.error) and not self._built:
            self._build_menu()
        if self.t < self.GRACE:
            return
        if self.game.input.pressed("back"):
            ui.sfx("back")
            return self._close()
        if self.menu:
            self.menu.update(self.game.input)

    def _lines(self) -> list[tuple[str, tuple]]:
        if self.task.error:
            return [("Não foi possível verificar.", ui.RED), (self.task.error[:70], ui.WHITE)]
        r = self.task.result
        if r is None:
            return []
        if r["state"] == "nomanifest":
            return [("Disponível só no jogo instalado (pelo instalador).", ui.ACCENT),
                    ("Rodando do código-fonte não há lista de arquivos para conferir.", ui.WHITE)]
        if r["state"] == "ok":
            extra = "" if r["hashed"] else "  (esta versão só confere se os arquivos existem)"
            return [(f"Tudo certo: {r['total']} arquivos conferidos." + extra, ui.GREEN)]
        out = [(f"{len(r['missing'])} ausente(s) e {len(r['modified'])} alterado(s) de {r['total']} arquivos.", ui.RED)]
        for name in (r["missing"] + r["modified"])[:4]:
            out.append((name[:64], (200, 200, 210)))
        if not can_self_update():
            out.append(("Reparo automático só no jogo instalado.", ui.ACCENT))
        return out

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._dim, (0, 0))
        off = int((1 - min(1.0, ease_out_back(min(1.0, self.t / 0.28)))) * 50)
        a = self.game.assets
        pr = self.panel.move(0, off)
        ui.panel(surf, pr, (20, 22, 32, 245))
        ui.text(surf, a.font(40), "Verificar arquivos", (pr.centerx, pr.y + 24), ui.ACCENT, "midtop")
        ui.text(surf, a.font(20, bold=False), f"Versão {local_version()}", (pr.centerx, pr.y + 78), (180, 180, 190), "midtop")
        if self.task.result is None and not self.task.error:
            ui.bar(surf, (pr.x + 80, pr.y + 170, pr.w - 160, 24), self.task.progress, ui.GREEN)
            ui.text(surf, a.font(22, bold=False), "Conferindo...", (pr.centerx, pr.y + 210), anchor="midtop")
            return
        for i, (line, col) in enumerate(self._lines()):
            ui.text(surf, a.font(24, bold=False), line, (pr.x + 40, pr.y + 130 + i * 38), col)
        if self.menu:
            for b in self.menu.buttons:
                b.rect.y = self.panel.bottom - 90 + off
            self.menu.draw(surf, a.font(28))


class RepairScene(Scene):
    """Baixa o pacote da versão instalada, confere o hash e roda o patcher (igual ao auto-update)."""

    def __init__(self, game) -> None:
        super().__init__(game)
        self.t = 0.0
        self.task = UpdateTask(game.cfg.get("update", {}))
        self.task.state, self.task.message = "starting", "Preparando..."

    def enter(self) -> None:
        cfg = self.task.cfg
        try:
            version = local_version()
            pkg, sha = rt.release_urls(cfg["repo"], version, cfg["asset_pattern"])
            self.task.info = UpdateInfo(version, "", pkg, sha)
            self.task.start_download()
        except Exception as e:  # noqa: BLE001
            self.task.state, self.task.message = "error", f"{type(e).__name__}: {e}"

    def update(self, dt: float) -> None:
        self.t += dt
        task = self.task
        if task.state == "ready":
            if task.apply_and_restart():
                self.game.quit()
            else:
                task.state, task.message = "error", "Reparo automático só no jogo instalado."
        elif task.state == "error" and (self.game.input.pressed("back") or self.game.input.pressed("confirm")):
            self.game.scenes.pop(fade=True)
        elif self.game.input.pressed("back") and task.state == "downloading":
            task.cancel()
            self.game.scenes.pop(fade=True)

    def draw(self, surf: pygame.Surface) -> None:
        W, H = surf.get_size()
        a = self.game.assets
        surf.fill((18, 20, 30))
        ui.text(surf, a.font(54), "Reparando o jogo", (W // 2, H // 2 - 120), ui.ACCENT, "center")
        ui.text(surf, a.font(24), self.task.message or "...", (W // 2, H // 2 + 10), anchor="center")
        if self.task.state == "downloading":
            ui.bar(surf, (W // 2 - 250, H // 2 + 50, 500, 22), self.task.progress, ui.GREEN)
        hint = "Esc / Enter para voltar" if self.task.state == "error" else "Esc cancela o download"
        ui.text(surf, a.font(16, bold=False), hint, (W // 2, H - 30), (150, 150, 160), "center")
