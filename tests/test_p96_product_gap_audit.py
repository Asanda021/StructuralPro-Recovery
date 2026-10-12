from pathlib import Path

def test_p96_audit_defines_real_production_depth_gaps():
    text=(Path(__file__).parents[1]/"docs"/"P96_PRODUCT_GAP_AUDIT.md").read_text(encoding="utf-8")
    for token in ("P97","P98","P99","P100","P101","P102","P103","P104","P105"):
        assert token in text or token.replace("P","P") in text
    assert "licensed official Iranian price-list" in text
    assert "Windows signing credentials" in text
