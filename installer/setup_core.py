"""Lógica do instalador, sem interface (usada pela janela, pelo modo silencioso e pelos testes).

Só biblioteca padrão. Tudo que mexe no sistema (atalhos, registro) é Windows-first,
com alternativa simples no Linux.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from network import release_tools as rt

APP_NAME = "UCDM Legends"
APP_ID = "UCDMLegends"            # chave em "Aplicativos instalados"
PUBLISHER = "UCDM"
ASSET_PATTERN = "UCDM-{platform}-v{version}.zip"
EXE = "UCDM.exe" if sys.platform == "win32" else "UCDM"
INSTALLER_EXE = "UCDM-Installer.exe" if sys.platform == "win32" else "UCDM-Installer"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"

# Preferências do jogo que o instalador oferece (mesmas chaves de assets/data/game.json).
DEFAULT_SETTINGS = {
    "display": {"fullscreen": False, "vsync": True, "fps_cap": 144, "show_fps": False},
    "audio": {"music_volume": 0.5, "sfx_volume": 0.8},
    "update": {"enabled": True},
}


# --- pastas ---------------------------------------------------------------------------------
def default_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "UCDM"
    return Path.home() / ".local" / "share" / "ucdm-game"


def user_dir() -> Path:
    """Mesmo local de core/paths.py: saves, mods, settings e logs do jogador."""
    if "UCDM_USER_DIR" in os.environ:
        return Path(os.environ["UCDM_USER_DIR"])
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "UCDM"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ucdm"


def shell_folder(csidl: int) -> Path | None:
    """Pastas reais do Windows (a Área de Trabalho pode estar no OneDrive ou em outro disco)."""
    if sys.platform != "win32":
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:
        return Path(buf.value)
    return None


def desktop_dir() -> Path:
    return shell_folder(0x0010) or Path.home() / "Desktop"            # CSIDL_DESKTOPDIRECTORY


def start_menu_dir() -> Path:
    return shell_folder(0x0002) or Path.home() / "Start Menu" / "Programs"   # CSIDL_PROGRAMS


def free_bytes(path: Path) -> int:
    p = Path(path).resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return 0


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())


def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def validate_dir(path: str) -> str | None:
    """Mensagem de erro, ou None se a pasta serve."""
    if not path.strip():
        return "Escolha uma pasta."
    p = Path(path).expanduser()
    if not p.is_absolute():
        return "Use um caminho completo (ex.: C:\\Jogos\\UCDM)."
    if p.exists() and not p.is_dir():
        return "Esse caminho é um arquivo, não uma pasta."
    if p.exists() and any(p.iterdir()) and not (p / "version.json").exists() and not (p / EXE).exists():
        return "A pasta já tem outros arquivos. Escolha uma pasta vazia ou nova."
    if len(p.parts) <= 1:
        return "Não instale na raiz do disco; use uma subpasta."
    return None


# --- instalação existente / configurações ----------------------------------------------------
def _reg_read() -> dict:
    if sys.platform != "win32":
        return {}
    import winreg
    out = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            for name in ("InstallLocation", "DisplayVersion"):
                try:
                    out[name] = winreg.QueryValueEx(k, name)[0]
                except OSError:
                    pass
    except OSError:
        pass
    return out


def installed_version(path: Path) -> str | None:
    try:
        return json.loads((Path(path) / "version.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


def find_existing() -> tuple[Path, str] | None:
    """(pasta, versão) de uma instalação já existente, se houver."""
    reg = _reg_read()
    for cand in (reg.get("InstallLocation"), default_dir()):
        if cand:
            v = installed_version(Path(cand))
            if v:
                return Path(cand), v
    return None


def load_settings() -> dict:
    """Preferências atuais (padrões + settings.json existente)."""
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        cur = json.loads((user_dir() / "settings.json").read_text(encoding="utf-8"))
        for sec, vals in cur.items():
            if isinstance(vals, dict):
                out.setdefault(sec, {}).update(vals)
    except (OSError, ValueError):
        pass
    return out


def save_settings(settings: dict) -> Path:
    """Mescla no settings.json do jogador (mantém chaves que o instalador não conhece)."""
    path = user_dir() / "settings.json"
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    for sec, vals in settings.items():
        cur.setdefault(sec, {}).update(vals)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


# --- Release no GitHub ----------------------------------------------------------------------
@dataclass
class ReleaseInfo:
    version: str
    package_url: str
    sha256_url: str
    size: int = 0
    notes: str = ""
    date: str = ""


def fetch_release(repo: str, timeout: float = 10) -> ReleaseInfo:
    data = rt.get_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout)
    version = data["tag_name"].lstrip("v")
    want = ASSET_PATTERN.format(platform=rt.platform_tag(), version=version)
    assets = {a["name"]: a for a in data.get("assets", [])}
    if want not in assets or want + ".sha256" not in assets:
        raise LookupError(f"A versão {version} não tem pacote para este sistema ({want}).")
    return ReleaseInfo(version, assets[want]["browser_download_url"], assets[want + ".sha256"]["browser_download_url"],
                       int(assets[want].get("size") or 0), (data.get("body") or "").strip(),
                       (data.get("published_at") or "")[:10])


# --- atalhos / registro ---------------------------------------------------------------------
def _make_lnk(lnk: Path, exe: Path, workdir: Path, description: str) -> None:
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:UCDM_LNK);"
          "$s.TargetPath=$env:UCDM_EXE;$s.WorkingDirectory=$env:UCDM_DIR;"
          "$s.IconLocation=$env:UCDM_EXE+',0';$s.Description=$env:UCDM_DESC;$s.Save()")
    env = dict(os.environ, UCDM_LNK=str(lnk), UCDM_EXE=str(exe), UCDM_DIR=str(workdir), UCDM_DESC=description)
    lnk.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, check=True,
                   capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def shortcut_paths() -> dict[str, Path]:
    return {"desktop": desktop_dir() / f"{APP_NAME}.lnk", "start_menu": start_menu_dir() / f"{APP_NAME}.lnk"}


def create_shortcuts(target: Path, desktop: bool, start_menu: bool, log: Callable[[str], None]) -> None:
    if sys.platform == "win32":
        exe = target / EXE
        for kind, wanted in (("desktop", desktop), ("start_menu", start_menu)):
            lnk = shortcut_paths()[kind]
            if not wanted:
                continue
            try:
                _make_lnk(lnk, exe, target, "Treine. Lute. Evolua.")
                log(f"Atalho criado: {lnk}")
            except (OSError, subprocess.SubprocessError) as e:
                log(f"Não foi possível criar o atalho {lnk.name}: {e}")
    elif sys.platform.startswith("linux") and (desktop or start_menu):
        apps = Path.home() / ".local" / "share" / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        cmd = " ".join(rt.game_command(target))
        (apps / "ucdm.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={cmd}\nPath={target}\n", encoding="utf-8")
        log("Atalho criado no menu de aplicativos")


def remove_shortcuts(log: Callable[[str], None]) -> None:
    for lnk in shortcut_paths().values():
        if lnk.exists():
            try:
                lnk.unlink()
                log(f"Atalho removido: {lnk}")
            except OSError as e:
                log(f"Não foi possível remover {lnk}: {e}")


def register_uninstall(target: Path, version: str) -> None:
    """Aparece em Configurações > Aplicativos instalados, com botão Desinstalar."""
    if sys.platform != "win32":
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        inst = target / INSTALLER_EXE
        vals = {
            "DisplayName": APP_NAME, "DisplayVersion": version, "Publisher": PUBLISHER,
            "InstallLocation": str(target), "DisplayIcon": f"{target / EXE},0",
            "UninstallString": f'"{inst}" --uninstall', "QuietUninstallString": f'"{inst}" --uninstall --silent',
            "InstallDate": time.strftime("%Y%m%d"),
        }
        for name, v in vals.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, v)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, int(dir_size(target) / 1024))
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, 1)


def update_registered_version(target: Path, version: str) -> None:
    """Depois de um auto-update: só atualiza a versão se o jogo estiver registrado nesta pasta."""
    reg = _reg_read()
    if reg.get("InstallLocation") and Path(reg["InstallLocation"]).resolve() == Path(target).resolve():
        register_uninstall(Path(target), version)


def unregister() -> None:
    if sys.platform != "win32":
        return
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


# --- tarefas longas -------------------------------------------------------------------------
class Cancelled(Exception):
    pass


@dataclass
class InstallOptions:
    target: Path
    desktop_shortcut: bool = True
    start_menu_shortcut: bool = True
    register: bool = True
    settings: dict | None = None
    log: Callable[[str], None] = print
    # progress(etapa, fração 0..1 da etapa, bytes_baixados, bytes_totais)
    progress: Callable[[str, float, int, int], None] = lambda *a: None
    cancel: Callable[[], bool] = lambda: False
    tmp_root: Path | None = None


def install(repo: str, rel: ReleaseInfo, o: InstallOptions) -> None:
    def check():
        if o.cancel():
            raise Cancelled()

    target = Path(o.target)
    o.log(f"Instalando {APP_NAME} {rel.version} em {target}")
    with tempfile.TemporaryDirectory(prefix="ucdm-install-", dir=o.tmp_root) as tmp:
        tmpd = Path(tmp)
        o.progress("download", 0.0, 0, rel.size)
        sha = rt.get_text(rel.sha256_url, 15)
        check()
        zip_path = rt.download(rel.package_url, tmpd / "pkg.zip",
                               lambda d, t: o.progress("download", d / t if t else 0.0, d, t or rel.size),
                               timeout=30, cancel=o.cancel)
        o.log(f"Download concluído ({fmt_size(zip_path.stat().st_size)})")
        o.progress("verify", 0.0, 0, 0)
        rt.verify_sha256(zip_path, sha)
        o.log("Integridade conferida (SHA-256 OK)")
        check()
        o.progress("extract", 0.0, 0, 0)
        root = rt.safe_extract(zip_path, tmpd / "pkg")
        o.log("Pacote extraído")
        check()
        o.progress("install", 0.0, 0, 0)
        rt.install_tree(root, target, o.log)   # a partir daqui não dá mais para cancelar
    o.progress("finish", 0.0, 0, 0)
    if o.settings is not None:
        o.log(f"Configurações salvas em {save_settings(o.settings)}")
    create_shortcuts(target, o.desktop_shortcut, o.start_menu_shortcut, o.log)
    if o.register:
        try:
            register_uninstall(target, rel.version)
            o.log('Registrado em "Aplicativos instalados" do Windows')
        except OSError as e:
            o.log(f"Não foi possível registrar no Windows: {e}")
    o.progress("finish", 1.0, 0, 0)
    o.log("Instalação concluída.")


def uninstall(target: Path, remove_user_data: bool, log: Callable[[str], None] = print) -> None:
    target = Path(target)
    remove_shortcuts(log)
    unregister()
    if target.is_dir():
        if not ((target / "version.json").exists() or (target / rt.MANIFEST).exists()):
            raise ValueError(f"{target} não parece ser uma instalação do {APP_NAME}; nada foi apagado.")
        for attempt in range(10):
            try:
                shutil.rmtree(target)
                break
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(0.5)   # o jogo pode estar fechando
        log(f"Pasta removida: {target}")
    if remove_user_data and user_dir().is_dir():
        shutil.rmtree(user_dir(), ignore_errors=True)
        log(f"Saves, mods e configurações removidos: {user_dir()}")
    log("Desinstalação concluída.")


def relaunch_from_temp(argv: list[str]) -> bool:
    """O desinstalador mora dentro da pasta que vai apagar: roda uma cópia a partir do %TEMP%."""
    if not getattr(sys, "frozen", False):
        return False
    me = Path(sys.executable).resolve()
    tmp = Path(tempfile.gettempdir()) / f"ucdm-uninstall-{os.getpid()}.exe"
    shutil.copy2(me, tmp)
    args = list(argv)
    if "--target" not in args:
        args += ["--target", str(me.parent)]
    rt.launch_detached([str(tmp), *args, "--self-delete"], Path(tempfile.gettempdir()))
    return True


def schedule_self_delete() -> None:
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        subprocess.Popen(f'cmd /c ping -n 4 127.0.0.1 >nul & del /f /q "{exe}"', shell=False,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                         cwd=tempfile.gettempdir())
