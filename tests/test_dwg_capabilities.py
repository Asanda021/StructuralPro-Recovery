from core.drawings.dwg_capabilities import detect_dwg_capabilities

def test_dwg_capability_object_is_explicit(monkeypatch):
    monkeypatch.setenv("STRUCTURALPRO_DWG_CONVERTER","/tmp/ODAFileConverter")
    c=detect_dwg_capabilities()
    assert c.converter=="/tmp/ODAFileConverter"
    assert c.converter_kind=="oda"
    assert "DWG" in c.message
