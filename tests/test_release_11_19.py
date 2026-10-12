import time
from core.search.command_center import command_search
from core.history.project_commands import ProjectHistory
from core.projects.backup import BackupManager
from core.performance.benchmark import benchmark_search,synthetic_project
from core.search.global_search import search_project
from core.ai.takeoff_assistant import LocalTakeoffAssistant,SafeTakeoffSuggestion
from core.licensing.license import LicenseManager

def test_search_and_undo():
 p={"name":"پروژه","takeoffs":[{"title":"طبقه دوم","quantities":[{"title":"دیوار","price_code":"A"}]}],"boq":[]}
 assert command_search(p,"دیوار")
 h=ProjectHistory(p);h.set_value(["name"],"نسخه دوم");assert p["name"]=="نسخه دوم";h.undo();assert p["name"]=="پروژه";h.redo();assert p["name"]=="نسخه دوم"

def test_backup(tmp_path):
 b=BackupManager(tmp_path);p={"name":"پروژه","x":[1,2]};path=b.create(p,"P1");assert b.restore(path)==p;assert b.list("P1");b.prune("P1",1)

def test_performance():
 p=synthetic_project(2000);r=benchmark_search(search_project,p,["دیوار","1999","طبقه"],max_seconds=2);assert r["passed"]

def test_ai_confirmation():
 a=LocalTakeoffAssistant();s=a.suggest_mapping([{"layer":"wall"}],[{"code":"1","description":"wall"}]);assert s
 assert SafeTakeoffSuggestion(a).explain(s[0])["requires_user_confirmation"]

def test_license():
 lm=LicenseManager("test-secret");t=lm.issue("demo",int(time.time())+3600,"PC1");assert lm.validate(t,"PC1")["valid"];assert not lm.validate(t,"PC2")["valid"]
