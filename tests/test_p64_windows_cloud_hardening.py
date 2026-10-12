from core.windows.product_v3 import WindowsRelease,WindowsWorkspace,release_manifest,manifest_fingerprint
from core.cloud.collaboration_v4 import Event,apply_event,three_way
def test_windows_release_is_production_grade():
 r=WindowsRelease("3.0.0","StructuralPro-3.0.0-x64.exe","StructuralPro.exe","a"*64,"x64","stable","Windows 10"); w=WindowsWorkspace(".spx",".bak",30,True,True); m=release_manifest(r,w); assert m["install"]["rollback"] and len(manifest_fingerprint(m))==64
def test_collaboration_roles_and_stale_events():
 e=Event("p",2,"u","editor","a"*64,{"qty":10},"update"); assert apply_event(1,"a"*64,e)["accepted"]; assert apply_event(2,"b"*64,e)["status"]=="stale_or_duplicate"
def test_conflict_is_fail_closed_and_three_way_is_explicit():
 e=Event("p",2,"u","editor","b"*64,{"qty":11},"update"); assert apply_event(1,"c"*64,e)["requires_review"]; assert "qty" in three_way({"qty":10},{"qty":11},{"qty":12})["conflicts"]
def test_viewer_cannot_mutate():
 try: apply_event(1,"x"*64,Event("p",2,"u","viewer","x"*64,{"a":1},"update")); assert False
 except ValueError: assert True
