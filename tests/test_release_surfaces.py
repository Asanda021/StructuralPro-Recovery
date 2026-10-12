from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_windows_packaging_surface_exists():
    assert (ROOT/"packaging/build_windows.ps1").exists()
    assert (ROOT/"packaging/structuralpro.spec").exists()

def test_android_client_surface_exists():
    assert (ROOT/"android/app/src/main/java/com/asanda/structuralpro/MainActivity.kt").exists()
    gradle=(ROOT/"android/app/build.gradle.kts").read_text()
    assert "androidx.compose" in gradle
    assert "minSdk = 29" in gradle
