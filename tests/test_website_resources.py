from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; PAGE=ROOT/"website"/"resources.html"; DATA=ROOT/"website"/"data"/"resources.json"
def test_catalog():
 d=json.loads(DATA.read_text(encoding="utf-8")); assert d["schema_version"]=="1.0"; assert len(d["items"])>=10
 assert all(i["title"].get("en") and i["title"].get("fa") for i in d["items"])
 assert all(i["description"].get("en") and i["description"].get("fa") for i in d["items"])
 assert all(i["status"] in {"Available","Planned","Integration"} for i in d["items"])
def test_targets():
 d=json.loads(DATA.read_text(encoding="utf-8"))
 for i in d["items"]:
  if i["status"]=="Available" and i["href"]: assert (PAGE.parent/i["href"]).resolve().exists()
def test_rtl_and_source():
 h=PAGE.read_text(encoding="utf-8"); assert 'lang="en" dir="ltr"' in h; assert 'get("lang")==="fa"' in h; assert "resources.html?lang=fa" in h; assert "data/resources.json" in h; assert "[dir=rtl]" in h
def test_no_fake_claims():
 h=PAGE.read_text(encoding="utf-8").lower(); assert not any(x in h for x in ["trusted by","certified by","award-winning","number one","best in class"])
