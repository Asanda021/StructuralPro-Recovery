from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_official_product_identity_fa():
    text = (ROOT / "docs/PRODUCT_IDENTITY_FA.md").read_text(encoding="utf-8")
    assert "مهندس محمد سلطانی" in text
    assert "ERVIRA.ir" in text
    assert "۱۴۰۵/۰۷/۱۴" in text

def test_official_product_identity_en():
    text = (ROOT / "docs/PRODUCT_IDENTITY_EN.md").read_text(encoding="utf-8")
    assert "Engineer Mohammad Soltani" in text
    assert "ERVIRA.ir" in text
    assert "1405/07/14" in text
