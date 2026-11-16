"""Monta o pacote de Release (usado pelo GitHub Actions e localmente).

    python installer/build_release.py --platform windows

Passos:
  1. PyInstaller: jogo (onedir, UCDM.exe) + instalador/patcher (onefile).
  2. Copia assets/ e version.json para FORA do exe (moddável, atualizável).
  3. Gera manifest.json (lista de arquivos — permite remover obsoletos no update).
  4. Compacta em dist/UCDM-<plataforma>-v<versão>.zip + .sha256.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from network import release_tools as rt  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'UCDM'),
      StringStruct('FileDescription', '{desc}'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', 'UCDM Legends'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'UCDM Legends'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])]
)
"""


def version_file(name: str, desc: str, version: str) -> Path:
    """Recurso de versão do Windows (Propriedades > Detalhes). Executável sem isso parece suspeito
    para antivírus por aprendizado de máquina."""
    nums = tuple((rt.parse_version(version) + (0, 0, 0, 0))[:4])
    out = BUILD / f"version_{name}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(VERSION_INFO.format(t=nums, v=version, name=name, desc=desc), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default=rt.platform_tag())
    ap.add_argument("--repo", default=None, help="dono/repo embutido no instalador e no game.json")
    ap.add_argument("--skip-pyinstaller", action="store_true", help="empacota o código-fonte (sem exe)")
    args = ap.parse_args()

    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))["version"]
    stage = DIST / "UCDM"
    if stage.exists():
        shutil.rmtree(stage)
    exe = ".exe" if args.platform == "windows" else ""

    if args.skip_pyinstaller:
        stage.mkdir(parents=True)
        for d in ("core", "entities", "systems", "minigames", "network", "installer", "scenes"):
            shutil.copytree(ROOT / d, stage / d, ignore=shutil.ignore_patterns("__pycache__"))
        for f in ("main.py", "requirements.txt"):
            shutil.copy2(ROOT / f, stage / f)
    else:
        inst_src = ROOT / "installer" / "ucdm_installer.py"
        if args.repo:   # embute o repositório real no instalador
            patched = BUILD / "installer_entry.py"   # build/ fica 1 nível abaixo da raiz, como installer/
            patched.parent.mkdir(parents=True, exist_ok=True)
            patched.write_text(inst_src.read_text(encoding="utf-8").replace(
                'DEFAULT_REPO = "KoZuuYT/ucdm-legends"', f'DEFAULT_REPO = "{args.repo}"'), encoding="utf-8")
            inst_src = patched
        icon = ROOT / "installer" / "art" / "icon.ico"
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
             "--icon", str(icon), "--exclude-module", "tkinter", "--exclude-module", "numpy",
             "--version-file", str(version_file("UCDM", "UCDM Legends", version)),
             "--name", "UCDM", "--distpath", str(DIST), "--workpath", str(BUILD / "game"),
             "--specpath", str(BUILD), "--paths", str(ROOT), "--collect-submodules", "minigames",
             "--collect-submodules", "scenes", str(ROOT / "main.py")])
        sep = ";" if sys.platform == "win32" else ":"
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
             "--icon", str(icon), "--add-data", f"{ROOT / 'installer' / 'art'}{sep}art",
             "--hidden-import", "installer.gui", "--hidden-import", "installer.setup_core",
             "--version-file", str(version_file("UCDM-Installer", "Instalador do UCDM Legends", version)),
             "--name", "UCDM-Installer", "--distpath", str(DIST), "--workpath", str(BUILD / "inst"),
             "--specpath", str(BUILD), "--paths", str(ROOT), str(inst_src)])
        shutil.copy2(DIST / f"UCDM-Installer{exe}", stage / f"UCDM-Installer{exe}")

    shutil.copytree(ROOT / "assets", stage / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "version.json", stage / "version.json")
    if args.repo:
        gj = stage / "assets" / "data" / "game.json"
        data = json.loads(gj.read_text(encoding="utf-8"))
        data["update"]["repo"] = args.repo
        gj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    rt.write_manifest(stage, version)

    name = f"UCDM-{args.platform}-v{version}.zip"
    zip_path = DIST / name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, Path("UCDM") / p.relative_to(stage))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (DIST / (name + ".sha256")).write_text(f"{digest}  {name}\n", encoding="utf-8")
    print(f"OK: {zip_path} ({zip_path.stat().st_size / 1048576:.1f} MB)\n    sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
