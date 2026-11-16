"""Ferramentas de release compartilhadas pelo jogo (auto-update) e pelo instalador.

SOMENTE biblioteca padrão — o instalador precisa ser minúsculo e não pode
depender de pygame. Segurança:
  * só baixa via HTTPS de domínios do GitHub;
  * todo pacote é verificado por SHA-256 (arquivo .sha256 publicado no Release);
  * extração protegida contra "zip slip" (caminhos ../ ou absolutos);
  * a aplicação do update troca arquivos de forma atômica e remove só o que
    a versão anterior instalou (manifest.json), nunca dados do jogador.
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

ALLOWED_HOSTS = {"github.com", "api.github.com", "raw.githubusercontent.com",
                 "objects.githubusercontent.com", "release-assets.githubusercontent.com",
                 "codeload.github.com"}
USER_AGENT = "UCDM-Updater/1.0"
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024   # 1 GB de teto de sanidade
MANIFEST = "manifest.json"

Progress = Callable[[int, int], None]


# --- versões ----------------------------------------------------------------------------
def parse_version(v: str) -> tuple[int, ...]:
    v = v.strip().lstrip("vV").split("-")[0].split("+")[0]
    parts = []
    for p in v.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def platform_tag() -> str:
    s = sys.platform
    if s == "win32":
        return "windows"
    if s == "darwin":
        return "macos"
    return "linux"


# --- HTTP -------------------------------------------------------------------------------
def _check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or (u.hostname or "") not in ALLOWED_HOSTS:
        raise ValueError(f"URL não permitida: {url}")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)   # GitHub redireciona downloads para *.githubusercontent.com
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirect)


def _open(url: str, timeout: float, accept: str | None = None):
    _check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if accept:
        req.add_header("Accept", accept)
    token = os.environ.get("UCDM_GITHUB_TOKEN")   # opcional: evita rate-limit em testes
    if token and urlparse(url).hostname == "api.github.com":
        req.add_header("Authorization", f"Bearer {token}")
    return _opener.open(req, timeout=timeout)


def get_json(url: str, timeout: float = 8) -> dict:
    with _open(url, timeout, "application/vnd.github+json") as r:
        return json.loads(r.read(4 * 1024 * 1024).decode("utf-8"))


def get_text(url: str, timeout: float = 8) -> str:
    with _open(url, timeout) as r:
        return r.read(64 * 1024).decode("utf-8")


def download(url: str, dest: Path, progress: Progress | None = None, timeout: float = 20,
             cancel: Callable[[], bool] | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    with _open(url, timeout) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        if total > MAX_PACKAGE_BYTES:
            raise ValueError("Pacote grande demais")
        done = 0
        while True:
            if cancel and cancel():
                raise InterruptedError("cancelado")
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done > MAX_PACKAGE_BYTES:
                raise ValueError("Pacote grande demais")
            if progress:
                progress(done, total)
    os.replace(part, dest)
    return dest


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, sha_text: str) -> None:
    expected = sha_text.strip().split()[0].lower()
    actual = sha256_file(path)
    if len(expected) != 64 or actual != expected:
        path.unlink(missing_ok=True)
        raise ValueError(f"Checksum inválido para {path.name} (esperado {expected[:12]}…, obtido {actual[:12]}…)")


# --- GitHub Releases --------------------------------------------------------------------
def release_urls(repo: str, version: str, pattern: str) -> tuple[str, str]:
    """URLs diretas (sem API, sem rate-limit) do pacote e do checksum de uma versão."""
    name = pattern.format(platform=platform_tag(), version=version.lstrip("v"))
    base = f"https://github.com/{repo}/releases/download/v{version.lstrip('v')}/{name}"
    return base, base + ".sha256"


def latest_release(repo: str, pattern: str, timeout: float = 8) -> tuple[str, str, str]:
    """(versão, url_pacote, url_sha256) do último Release publicado, via API."""
    data = get_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout)
    version = data["tag_name"].lstrip("v")
    want = pattern.format(platform=platform_tag(), version=version)
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    if want not in assets or want + ".sha256" not in assets:
        raise LookupError(f"Release {version} não tem '{want}' (+ .sha256) para esta plataforma")
    return version, assets[want], assets[want + ".sha256"]


# --- extração / aplicação ---------------------------------------------------------------
def safe_extract(zip_path: Path, dest: Path) -> Path:
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        total = sum(i.file_size for i in z.infolist())
        if total > MAX_PACKAGE_BYTES * 3:
            raise ValueError("Conteúdo descompactado grande demais")
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest):
                raise ValueError(f"Caminho inseguro no pacote: {info.filename}")
        z.extractall(dest)
    # Se o zip tiver uma única pasta raiz (ex.: UCDM/), desce nela.
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def _read_manifest(d: Path) -> set[str]:
    try:
        return set(json.loads((d / MANIFEST).read_text(encoding="utf-8"))["files"])
    except (OSError, ValueError, KeyError):
        return set()


def write_manifest(root: Path, version: str) -> Path:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != MANIFEST)
    # "hashes" (sha256 de cada arquivo) permite ao jogo verificar a instalação; manifests antigos só têm "files".
    hashes = {rel: sha256_file(root / rel) for rel in files}
    out = root / MANIFEST
    out.write_text(json.dumps({"version": version, "files": files, "hashes": hashes}, indent=1), encoding="utf-8")
    return out


def _replace_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".new")
    shutil.copy2(src, tmp)
    for attempt in range(20):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            # Windows: executável/DLL em uso pode ser RENOMEADO, mas não sobrescrito.
            try:
                old = dst.with_name(dst.name + ".old")
                old.unlink(missing_ok=True)
                os.replace(dst, old)
            except OSError:
                time.sleep(0.25)
    raise PermissionError(f"Não foi possível substituir {dst}")


def install_tree(src: Path, target: Path, log: Callable[[str], None] = print) -> None:
    """Copia a nova versão por cima da instalação e remove arquivos obsoletos."""
    target.mkdir(parents=True, exist_ok=True)
    old_files = _read_manifest(target)
    new_files = _read_manifest(src) or {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
    for rel in sorted(new_files):
        s = src / rel
        if s.is_file():
            _replace_file(s, target / rel)
    for rel in sorted(old_files - new_files):
        p = (target / rel).resolve()
        if p.is_relative_to(target.resolve()) and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
    if (src / MANIFEST).exists():
        shutil.copy2(src / MANIFEST, target / MANIFEST)
    for leftover in target.rglob("*.old"):
        try:
            leftover.unlink()
        except OSError:
            pass
    log(f"{len(new_files)} arquivos instalados em {target}")


def wait_for_pid(pid: int, timeout: float = 30) -> None:
    end = time.time() + timeout
    if sys.platform == "win32":
        import ctypes
        SYNCHRONIZE = 0x00100000
        h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if h:
            ctypes.windll.kernel32.WaitForSingleObject(h, int(timeout * 1000))
            ctypes.windll.kernel32.CloseHandle(h)
        return
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def game_command(install_dir: Path) -> list[str]:
    exe = install_dir / ("UCDM.exe" if sys.platform == "win32" else "UCDM")
    if exe.exists():
        return [str(exe)]
    return [sys.executable, str(install_dir / "main.py")]


def launch_detached(cmd: list[str], cwd: Path) -> None:
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, cwd=str(cwd), close_fds=True, **kw)


def describe() -> str:
    return f"{platform.system()} {platform.machine()} / Python {platform.python_version()}"
