"""UCDM Installer: instalador gráfico, desinstalador e patcher (só biblioteca padrão).

Modos:
  UCDM-Installer.exe                       abre o assistente de instalação (janela)
  UCDM-Installer.exe --silent [--dir P] [--no-shortcut] [--no-register] [--launch]
                                           instala sem janela (log em %TEMP%/ucdm-installer.log)
  UCDM-Installer.exe --uninstall [--silent] [--wipe-data]
                                           desinstala (é o que "Aplicativos instalados" chama)
  UCDM-Installer.exe --apply STAGING --target PASTA [--wait-pid PID] [--relaunch]
                                           usado pelo jogo no auto-update: espera fechar, troca os arquivos, reabre

Empacotado como .exe de arquivo único (sem console) pelo workflow .github/workflows/release.yml.
"""
import argparse
import sys
import tempfile
from pathlib import Path

# Permite rodar como script (python installer/ucdm_installer.py) e congelado (PyInstaller).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from installer import setup_core as sc  # noqa: E402
from network import release_tools as rt  # noqa: E402

# Substituído automaticamente no build do Release (workflow) pelo repositório real.
DEFAULT_REPO = "KoZuuYT/ucdm-legends"
LOG_FILE = Path(tempfile.gettempdir()) / "ucdm-installer.log"


class _Log:
    """Escreve no console (se existir) e num arquivo, para diagnosticar instalações sem janela."""

    def __init__(self, path: Path) -> None:
        self.f = open(path, "a", encoding="utf-8")

    def __call__(self, msg: str) -> None:
        if sys.stdout is not None:
            try:
                print(msg, flush=True)
            except (OSError, UnicodeError):
                pass
        self.f.write(msg + "\n")
        self.f.flush()


def silent_install(args, log) -> int:
    repo = args.repo or DEFAULT_REPO
    target = Path(args.dir) if args.dir else (sc.find_existing() or (sc.default_dir(), ""))[0]
    err = sc.validate_dir(str(target))
    if err:
        log(f"ERRO: {err}")
        return 2
    log(f"== {sc.APP_NAME} — instalação silenciosa ==  {rt.describe()}  repo={repo}")
    rel = sc.fetch_release(repo)
    last = [-1]

    def prog(stage, frac, done, total):
        pct = int(frac * 100)
        if stage == "download" and pct // 10 != last[0]:
            last[0] = pct // 10
            log(f"  download {pct}%  ({sc.fmt_size(done)} de {sc.fmt_size(total)})")

    sc.install(repo, rel, sc.InstallOptions(
        target=target, desktop_shortcut=not args.no_shortcut, start_menu_shortcut=not args.no_shortcut,
        register=not args.no_register, settings=sc.load_settings(), log=log, progress=prog))
    if args.launch:
        rt.launch_detached(rt.game_command(target), target)
    return 0


def uninstall(args, log) -> int:
    target = Path(args.target) if args.target else None
    if target is None:
        found = sc.find_existing()
        target = found[0] if found else None
    # O desinstalador fica dentro da pasta que vai apagar: continua a partir de uma cópia no %TEMP%.
    if getattr(sys, "frozen", False) and target and Path(sys.executable).resolve().is_relative_to(target.resolve()):
        if sc.relaunch_from_temp(sys.argv[1:] + ([] if args.target else ["--target", str(target)])):
            return 0
    try:
        if args.silent:
            if target:
                sc.uninstall(target, args.wipe_data, log)
            else:
                sc.remove_shortcuts(log)
            return 0
        from installer import gui
        return gui.run(args.repo or DEFAULT_REPO, "uninstall", target)
    finally:
        if args.self_delete:
            sc.schedule_self_delete()


def apply(args, log) -> int:
    staging, target = Path(args.apply), Path(args.target)
    try:
        if args.wait_pid:
            log(f"Aguardando o jogo (pid {args.wait_pid}) fechar...")
            rt.wait_for_pid(int(args.wait_pid))
        rt.install_tree(staging, target, log)
        v = sc.installed_version(target)
        if v:
            try:
                sc.update_registered_version(target, v)
            except OSError:
                pass
        log("Update aplicado com sucesso.")
        code = 0
    except Exception as e:  # mantém log para diagnóstico; o jogo antigo continua íntegro
        log(f"FALHA ao aplicar update: {type(e).__name__}: {e}")
        code = 1
    if args.relaunch:
        rt.launch_detached(rt.game_command(target), target)
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{sc.APP_NAME} installer/patcher")
    ap.add_argument("--repo")
    ap.add_argument("--dir")
    ap.add_argument("--silent", "--yes", "-y", action="store_true", help="sem janela")
    ap.add_argument("--no-shortcut", action="store_true")
    ap.add_argument("--no-register", action="store_true")
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--wipe-data", action="store_true")
    ap.add_argument("--self-delete", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--apply")
    ap.add_argument("--target")
    ap.add_argument("--wait-pid")
    ap.add_argument("--relaunch", action="store_true")
    args = ap.parse_args(argv)

    if args.apply:
        if not args.target:
            ap.error("--apply exige --target")
        log = _Log(Path(args.apply).parent / "update.log")
        return apply(args, log)
    log = _Log(LOG_FILE)
    try:
        if args.uninstall:
            return uninstall(args, log)
        if args.silent:
            return silent_install(args, log)
        from installer import gui
        return gui.run(args.repo or DEFAULT_REPO, "install", Path(args.dir) if args.dir else None)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001
        log(f"ERRO: {type(e).__name__}: {e}")
        if not args.silent:
            try:
                from tkinter import messagebox
                messagebox.showerror(sc.APP_NAME, f"{type(e).__name__}: {e}\n\nLog: {LOG_FILE}")
            except Exception:  # noqa: BLE001
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
