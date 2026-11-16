"""Ponto de entrada do jogo.

    python main.py                 # jogo normal (checa updates no boot)
    python main.py --skip-update   # pula a checagem
    python main.py --scene arena   # atalho de desenvolvimento (arena/slash/shield/agility/focus/hub)
    python main.py --headless --frames 300   # smoke test sem janela (CI)
"""
import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="UCDM Legends")
    ap.add_argument("--skip-update", action="store_true")
    ap.add_argument("--scene", default=None)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--frames", type=int, default=None)
    args = ap.parse_args(argv)

    from core.engine import Game
    game = Game(headless=args.headless)

    if args.scene:
        from entities.progression import Profile
        data = game.save.load_raw()
        game.profile = Profile.from_dict(data) if data else Profile(character=game.cfg["default_character"])
        first = _dev_scene(game, args.scene)
    elif args.skip_update:
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
    if name == "select":
        from scenes.character_select import CharacterSelectScene
        return CharacterSelectScene(game, new_game=False)
    from scenes.hub import HubScene
    return HubScene(game)


if __name__ == "__main__":
    sys.exit(main())
