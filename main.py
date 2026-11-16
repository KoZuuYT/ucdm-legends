"""Ponto de entrada do jogo.

    python main.py                 # jogo normal (checa updates no boot)
    python main.py --skip-update   # pula a checagem
    python main.py --scene arena   # atalho de desenvolvimento (arena/slash/shield/agility/focus/hub)
    python main.py --headless --frames 300   # smoke test sem janela (CI)
"""
import argparse
import sys
import traceback


def _setup_logging() -> None:
    """No .exe (sem console) stdout/stderr não existem: tudo vai para logs/game.log."""
    from core import paths
    paths.ensure_user_dirs()
    if paths.FROZEN or sys.stdout is None:
        log = open(paths.LOG_DIR / "game.log", "w", encoding="utf-8", buffering=1, errors="replace")
        sys.stdout = sys.stderr = log


def _report_crash(exc: BaseException) -> None:
    from core import paths
    text = "".join(traceback.format_exception(exc))
    path = paths.LOG_DIR / "crash.log"
    try:
        paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass
    print(text, file=sys.stderr)
    if sys.platform == "win32" and paths.FROZEN:
        import ctypes
        msg = (f"O jogo encontrou um erro e precisou fechar.\n\n{type(exc).__name__}: {exc}\n\n"
               f"Detalhes salvos em:\n{path}")
        ctypes.windll.user32.MessageBoxW(None, msg, "UCDM Legends", 0x10)


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    try:
        return _main(argv)
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 — qualquer erro vira crash.log + aviso
        _report_crash(e)
        return 1


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="UCDM Legends")
    ap.add_argument("--skip-update", action="store_true")
    ap.add_argument("--scene", default=None)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--frames", type=int, default=None)
    args = ap.parse_args(argv)

    from core import paths
    from core.engine import Game
    game = Game(headless=args.headless)

    if args.scene:
        from entities.progression import Profile
        data = game.save.load_raw()
        game.profile = Profile.from_dict(data) if data else Profile()
        first = _dev_scene(game, args.scene)
    elif args.skip_update or paths.ANDROID:     # no celular não há checagem de atualização (baixe o novo APK)
        from scenes.menu import MenuScene
        first = MenuScene(game)
    else:
        from scenes.boot import BootScene
        first = BootScene(game)
    game.run(first, max_frames=args.frames)
    return 0


def _dev_scene(game, name: str):
    from minigames import REGISTRY
    if name in REGISTRY:
        return REGISTRY[name](game)
    if name == "arena":
        from entities import roster
        from scenes.arena import ArenaScene
        return ArenaScene(game, min(game.profile.arena_stage, len(roster.enemies()) - 1))
    if name in ("select", "collection"):
        from scenes.collection import CollectionScene
        return CollectionScene(game)
    from scenes.hub import HubScene
    return HubScene(game)


if __name__ == "__main__":
    sys.exit(main())
