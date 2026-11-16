"""Informações do sistema para relatos de bug. NUNCA inclui nome de usuário, caminhos completos ou saves."""
import platform
import sys

import pygame

from core import i18n, paths


def collect(game) -> str:
    from network.updater import local_version
    disp = game.cfg.get("display", {})
    lines = [
        f"UCDM Legends {local_version()} ({'instalado' if paths.FROZEN else 'código-fonte'})",
        f"Sistema: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python {sys.version.split()[0]}  pygame-ce {pygame.version.ver}  SDL {'.'.join(map(str, pygame.get_sdl_version()))}",
        f"Tela: {game.display.width}x{game.display.height}  janela {game.display.window_size()[0]}x{game.display.window_size()[1]}"
        f"  fullscreen={game.display.fullscreen}  vsync={disp.get('vsync')}  fps_cap={disp.get('fps_cap')}",
        f"FPS atual: {game.fps:.0f}  áudio: {'ligado' if game.audio.enabled else 'desligado'}  idioma: {i18n.language()}",
        f"Baixo desempenho: {game.low_perf}  controles conectados: {pygame.joystick.get_count() if pygame.joystick.get_init() else 0}",
        f"Texturas: {game.assets.stats()}",
    ]
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    try:
        pygame.scrap.put_text(text)
        return True
    except (pygame.error, AttributeError, NotImplementedError):
        return False


def save_to_file(text: str):
    path = paths.LOG_DIR / "system-info.txt"
    paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path
