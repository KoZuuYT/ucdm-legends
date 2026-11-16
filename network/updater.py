"""Auto-update in-game (roda numa thread para não travar a tela de boot).

Fluxo:
 1. Lê version.json local e o version.json do branch no GitHub (raw).
 2. Se remoto > local: baixa o pacote do Release v<versão> + .sha256 e verifica.
 3. Extrai em <USER_DIR>/update/staging-<versão> (zip-slip safe).
 4. Lança o patcher (UCDM-Installer --apply) que espera o jogo fechar,
    substitui os arquivos e reabre o jogo.

Em modo desenvolvimento (rodando do código-fonte) o update NUNCA é aplicado
automaticamente sobre o seu repositório — só é avisado. Para testar o fluxo
completo defina UCDM_FORCE_UPDATE=1 e UCDM_INSTALL_DIR=<pasta de teste>.
"""
import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from core import paths
from network import release_tools as rt


@dataclass
class UpdateInfo:
    version: str
    notes: str
    package_url: str
    sha256_url: str


def local_version() -> str:
    try:
        return json.loads(paths.VERSION_FILE.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "0.0.0"


def channel_branch(cfg: dict) -> str:
    """Canal de atualização: "estavel" lê o branch principal; "beta" lê o branch `beta` (se existir)."""
    return "beta" if cfg.get("channel") == "beta" else cfg.get("branch", "main")


def can_rollback() -> bool:
    return can_self_update() and rt.has_backup(install_dir())


def start_rollback() -> bool:
    """Lança o instalador em modo --rollback e retorna True se o jogo deve fechar agora."""
    if not can_rollback():
        return False
    st = install_dir()
    exe = st / ("UCDM-Installer.exe" if sys.platform == "win32" else "UCDM-Installer")
    cmd = [str(exe)] if exe.exists() else [sys.executable, str(st / "installer" / "ucdm_installer.py")]
    cmd += ["--rollback", "--target", str(st), "--relaunch"]
    rt.launch_detached(cmd, paths.UPDATE_DIR)
    return True


def can_self_update() -> bool:
    return paths.FROZEN or os.environ.get("UCDM_FORCE_UPDATE") == "1"


def install_dir() -> Path:
    return Path(os.environ.get("UCDM_INSTALL_DIR", paths.BASE_DIR))


class UpdateTask:
    """Máquina de estados observável pela UI: checking -> (none|available) -> downloading -> ready|error."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.state = "idle"
        self.message = ""
        self.progress = 0.0
        self.info: UpdateInfo | None = None
        self.staging: Path | None = None
        self._cancel = False
        self._pause = False
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        repo = self.cfg.get("repo", "")
        return bool(self.cfg.get("enabled")) and "/" in repo and not repo.startswith("SEU_")

    def start_check(self) -> None:
        if not self.enabled:
            off = "/" in self.cfg.get("repo", "") and not self.cfg.get("enabled")
            self.state, self.message = "none", ("Atualizações automáticas desativadas" if off
                                               else "Atualização automática não configurada")
            return
        self._run(self._check)

    def start_download(self) -> None:
        self._run(self._download)

    def cancel(self) -> None:
        self._cancel = True

    def pause(self) -> None:
        """Pausa o download mantendo o que já foi baixado (.part)."""
        if self.state == "downloading":
            self._pause = True

    def resume(self) -> None:
        if self.state == "paused":
            self._pause = False
            self.start_download()

    def toggle_pause(self) -> None:
        self.resume() if self.state == "paused" else self.pause()

    def _run(self, fn) -> None:
        self._thread = threading.Thread(target=self._guard, args=(fn,), daemon=True)
        self._thread.start()

    def _guard(self, fn) -> None:
        try:
            fn()
        except InterruptedError:
            if self._pause and not self._cancel:
                self.state, self.message = "paused", "Download pausado"
            else:
                self.state, self.message = "error", "Download cancelado"
        except Exception as e:  # rede caiu, release incompleto etc.: o jogo segue offline
            self.state, self.message = "error", f"{type(e).__name__}: {e}"
            print(f"[update] {self.message}")

    def _check(self) -> None:
        self.state, self.message = "checking", "Procurando atualizações..."
        repo, branch = self.cfg["repo"], channel_branch(self.cfg)
        timeout = self.cfg.get("timeout", 6)
        remote = json.loads(rt.get_text(f"https://raw.githubusercontent.com/{repo}/{branch}/version.json", timeout))
        local = local_version()
        if not rt.is_newer(remote["version"], local):
            self.state, self.message = "none", f"Versão {local} está atualizada"
            return
        pkg, sha = rt.release_urls(repo, remote["version"], self.cfg["asset_pattern"])
        self.info = UpdateInfo(remote["version"], remote.get("notes", ""), pkg, sha)
        self.state = "available"
        self.message = f"Nova versão {remote['version']} disponível (atual {local})"

    def _download(self) -> None:
        info = self.info
        assert info is not None
        self.state, self.message = "downloading", f"Baixando versão {info.version}..."
        timeout = self.cfg.get("timeout", 6) * 3
        sha_text = rt.get_text(info.sha256_url, timeout)
        zip_path = paths.UPDATE_DIR / f"ucdm-{info.version}.zip"

        def prog(done, total):
            self.progress = done / total if total else 0.0

        self._pause = False
        rt.download(info.package_url, zip_path, prog, timeout, cancel=lambda: self._cancel or self._pause)
        self.message = "Verificando integridade..."
        rt.verify_sha256(zip_path, sha_text)
        self.message = "Preparando arquivos..."
        self.staging = rt.safe_extract(zip_path, paths.UPDATE_DIR / f"staging-{info.version}")
        zip_path.unlink(missing_ok=True)
        self.state, self.message = "ready", "Atualização pronta. Reiniciando..."

    def apply_and_restart(self) -> bool:
        """Lança o patcher a partir do staging (versão NOVA do patcher) e retorna True
        se o jogo deve fechar agora."""
        if self.staging is None or not can_self_update():
            return False
        st = self.staging
        exe = st / ("UCDM-Installer.exe" if sys.platform == "win32" else "UCDM-Installer")
        if exe.exists():
            cmd = [str(exe)]
        else:
            cmd = [sys.executable, str(st / "installer" / "ucdm_installer.py")]
        cmd += ["--apply", str(st), "--target", str(install_dir()), "--wait-pid", str(os.getpid()), "--relaunch"]
        rt.launch_detached(cmd, paths.UPDATE_DIR)
        return True
