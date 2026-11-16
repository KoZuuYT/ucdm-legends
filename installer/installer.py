"""UCDM Installer — instalador e patcher minimalista (só biblioteca padrão).

Modos:
  Instalar (padrão):  UCDM-Installer.exe [--dir PASTA] [--repo dono/repo] [--yes] [--no-shortcut]
      Busca o último Release no GitHub, baixa o pacote da plataforma, confere o
      SHA-256, extrai e cria atalho na Área de Trabalho.
  Aplicar update:     UCDM-Installer.exe --apply STAGING --target PASTA [--wait-pid PID] [--relaunch]
      Usado pelo próprio jogo: espera o jogo fechar, troca os arquivos, reabre.

Empacotado como .exe de arquivo único pelo workflow .github/workflows/release.yml.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Permite rodar como script (python installer/installer.py) e congelado (PyInstaller).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from network import release_tools as rt  # noqa: E402

# Substituído automaticamente no build do Release (workflow) pelo repositório real.
DEFAULT_REPO = "SEU_USUARIO/SEU_REPOSITORIO"
ASSET_PATTERN = "UCDM-{platform}-v{version}.zip"
APP_NAME = "UCDM Legends"


def default_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "UCDM"
    return Path.home() / ".local" / "share" / "ucdm-game"


def bar(done: int, total: int) -> None:
    if total:
        k = done / total
        sys.stdout.write(f"\r  [{'#' * int(k * 30):<30}] {k * 100:5.1f}%  {done / 1048576:6.1f} MB")
    else:
        sys.stdout.write(f"\r  {done / 1048576:6.1f} MB")
    sys.stdout.flush()


def create_shortcut(target_dir: Path) -> None:
    cmd = rt.game_command(target_dir)
    if sys.platform == "win32":
        desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        lnk = desktop / f"{APP_NAME}.lnk"
        # Atalho .lnk via COM do Windows Script Host (sem dependências).
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:UCDM_LNK);"
              "$s.TargetPath=$env:UCDM_EXE;$s.WorkingDirectory=$env:UCDM_DIR;$s.Save()")
        env = dict(os.environ, UCDM_LNK=str(lnk), UCDM_EXE=cmd[0], UCDM_DIR=str(target_dir))
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env,
                           check=True, capture_output=True, timeout=30)
            print(f"  Atalho criado: {lnk}")
        except (OSError, subprocess.SubprocessError) as e:
            print(f"  (não foi possível criar o atalho: {e})")
    elif sys.platform.startswith("linux"):
        apps = Path.home() / ".local" / "share" / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        (apps / "ucdm.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={' '.join(cmd)}\nPath={target_dir}\n",
            encoding="utf-8")
        print("  Atalho criado no menu de aplicativos")


def install(args) -> int:
    repo = args.repo or DEFAULT_REPO
    target = Path(args.dir) if args.dir else default_dir()
    print(f"== {APP_NAME} — Instalador ==\n  Sistema: {rt.describe()}\n  Repositório: {repo}\n  Destino: {target}")
    if repo.startswith("SEU_"):
        print("ERRO: repositório não configurado (use --repo dono/repositorio).")
        return 2
    if not args.yes:
        if input("Continuar? [S/n] ").strip().lower() in ("n", "nao", "não", "no"):
            return 1
    print("Consultando último Release...")
    version, pkg_url, sha_url = rt.latest_release(repo, ASSET_PATTERN)
    print(f"  Versão {version}")
    with tempfile.TemporaryDirectory(prefix="ucdm-install-") as tmp:
        tmpd = Path(tmp)
        sha = rt.get_text(sha_url)
        zip_path = rt.download(pkg_url, tmpd / "pkg.zip", bar)
        print("\nVerificando SHA-256...")
        rt.verify_sha256(zip_path, sha)
        print("Extraindo...")
        root = rt.safe_extract(zip_path, tmpd / "pkg")
        rt.install_tree(root, target)
    if not args.no_shortcut:
        create_shortcut(target)
    print(f"\nPronto! {APP_NAME} {version} instalado.")
    if args.yes or input("Abrir o jogo agora? [S/n] ").strip().lower() not in ("n", "nao", "não", "no"):
        rt.launch_detached(rt.game_command(target), target)
    return 0


def apply(args) -> int:
    staging, target = Path(args.apply), Path(args.target)
    log_path = staging.parent / "update.log"
    with open(log_path, "a", encoding="utf-8") as log:
        def say(msg):
            print(msg)
            log.write(msg + "\n")
        try:
            if args.wait_pid:
                say(f"Aguardando o jogo (pid {args.wait_pid}) fechar...")
                rt.wait_for_pid(int(args.wait_pid))
            rt.install_tree(staging, target, say)
            say("Update aplicado com sucesso.")
        except Exception as e:  # mantém log para diagnóstico; o jogo antigo continua íntegro
            say(f"FALHA ao aplicar update: {type(e).__name__}: {e}")
            if args.relaunch:
                rt.launch_detached(rt.game_command(target), target)
            return 1
    if args.relaunch:
        rt.launch_detached(rt.game_command(target), target)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{APP_NAME} installer/patcher")
    ap.add_argument("--dir")
    ap.add_argument("--repo")
    ap.add_argument("--yes", "-y", action="store_true")
    ap.add_argument("--no-shortcut", action="store_true")
    ap.add_argument("--apply")
    ap.add_argument("--target")
    ap.add_argument("--wait-pid")
    ap.add_argument("--relaunch", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.apply:
            if not args.target:
                ap.error("--apply exige --target")
            return apply(args)
        return install(args)
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except Exception as e:
        print(f"\nERRO: {type(e).__name__}: {e}")
        if not args.yes and not args.apply:
            input("Pressione Enter para sair...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
