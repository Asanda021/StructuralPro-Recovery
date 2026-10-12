from pathlib import Path
from core.commercial.contract import Contract,ContractItem
from core.commercial.statement import build_payment_statement
from core.projects.library import ProjectLibrary
from core.sync.manager import SyncManager
from core.ai.project_assistant import ProjectAssistant
from core.drawings.unified_takeoff import UnifiedDrawingTakeoff

class Store:
    def __init__(self): self.data={}
    def list(self): return list(self.data.values())
    def get(self,k): return self.data.get(k)
    def save(self,p): self.data[p["id"]]=p; return p
    def revisions(self,k): return []

def test_second_five_core_surfaces(tmp_path):
    c=Contract("C","T",[ContractItem("1","x","m3",2,10)],overhead_rate=.1,regional_rate=.05,tax_rate=.09,insurance_rate=.03)
    result=build_payment_statement(c,[],previous_paid=0)
    assert result["commercial_total_current"]==0 and result["payable"]==0
    s=Store(); s.save({"id":"p1","name":"Alpha","takeoffs":[],"boq":[]})
    lib=ProjectLibrary(s); assert lib.search("alpha")[0]["id"]=="p1"
    lib.clone("p1","p2"); assert s.get("p2")
    assert SyncManager().sync()["status"]=="offline"
    assert ProjectAssistant().compare_rows([{"price_code":"A","quantity":2}],[{"price_code":"A","quantity":3}])[0]["delta"]==1
    try: UnifiedDrawingTakeoff().inspect(tmp_path/"missing.pdf")
    except FileNotFoundError: pass
    else: raise AssertionError("missing drawing must fail clearly")

def test_release_artifacts():
    root=Path(__file__).resolve().parents[1]
    assert (root/"packaging/build_windows.ps1").exists()
    assert (root/"android/app/src/main/java/com/asanda/structuralpro/MainActivity.kt").exists()
