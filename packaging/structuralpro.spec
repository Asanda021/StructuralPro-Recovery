from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd()

if not (ROOT / "app" / "main.py").exists():
    raise FileNotFoundError(f"Application entrypoint not found under {ROOT}")

hiddenimports = collect_submodules("core")
a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    hiddenimports=hiddenimports,
    datas=[(str(ROOT / "VERSION"), ".")],
    binaries=[],
    cipher=None,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="StructuralPro", console=False)