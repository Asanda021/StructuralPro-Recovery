from core.acceptance.p121_p130 import *
def test_p121_p130_all_green():
 r=run_all(); assert r["all_green"] and all(r["checks"].values())
def test_p122_tamper_fails():
 p={"id":"X"}; b=export_project(p); b["project"]["id"]="Y"
 try: import_project(b); assert False
 except ValueError: pass
def test_p124_redacts_nested_secrets():
 assert redact({"authorization":"Bearer x","nested":{"api_key":"x","ok":1}})["nested"]["api_key"]=="***REDACTED***"
def test_p125_invalid_lifecycle_fails():
 try: transition("archived","active"); assert False
 except ValueError: pass
def test_p128_blocks_insecure_and_traversal():
 assert not security_check({"scheme":"http","path":"projects/P1","project_id":"P1"})["safe"]
 assert not security_check({"scheme":"https","path":"../P1","project_id":"P1"})["safe"]
