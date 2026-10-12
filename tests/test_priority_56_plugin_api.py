from core.platform.plugins import PluginManifest, build_plugin_registry, discover_plugins

def plugin(pid="boq.export"):
    return PluginManifest(pid, "Example", "1.0.0", capabilities=("export","boq"),
                          publisher="publisher", license="MIT")

def test_valid_registry_is_deterministic():
    a=build_plugin_registry([plugin("zz"),plugin("aa")])
    b=build_plugin_registry([plugin("aa"),plugin("zz")])
    assert a["valid"] is True
    assert a["plugins"][0]["plugin_id"]=="aa"
    assert a["sha256"]==b["sha256"]

def test_invalid_manifest_fails_closed():
    bad=PluginManifest("BAD ID","","",publisher="",license="")
    r=build_plugin_registry([bad])
    assert r["valid"] is False

def test_duplicate_plugin_ids_rejected():
    r=build_plugin_registry([plugin("x"),plugin("X")])
    assert r["valid"] is False
    assert any("duplicate plugin_id" in e for e in r["errors"])

def test_capability_discovery_is_metadata_only():
    r=discover_plugins([plugin("xx"),plugin("yy")], "export")
    assert [x["plugin_id"] for x in r]==["xx","yy"]
