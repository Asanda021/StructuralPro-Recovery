# Windows packaging
StructuralPro desktop is packaged from `app/main.py` with PyInstaller.

Recommended release build (on Windows):

```powershell
py -3.12 -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onedir --windowed --name StructuralPro app/main.py
```

The resulting `dist/StructuralPro/` directory is the portable application payload.
For a signed installer, wrap this directory with the organization's preferred Windows installer/signing pipeline.

The application remains offline-first; packaging does not add a cloud dependency.
