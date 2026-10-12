"""Production acceptance for P111-P115: data, reports, revisions, scale and release."""
from __future__ import annotations
from pathlib import Path
import tempfile
from core.iran.data_pack import DataPackEntry,IranDataPack
from core.reports.production import prepare_report,totals
from core.reports.exporters import export_xlsx,export_pdf,export_docx
from core.revisions.impact import build_impact_report
from core.performance.project_performance import project_performance_snapshot,paginate
from core.performance.hardening import run_hardening_checks
from core.platform.release import load_version,ReleaseInfo

def run_data_pack():
    # Controlled sample only; never represented as an official Iranian dataset.
    pack=IranDataPack([DataPackEntry("SAMPLE-001","نمونه بتن","controlled-fixture","2026","abc","fixture-only")],"acceptance-1")
    manifest=pack.manifest()
    return {"verified":pack.verify(manifest),"official":False,"manifest":manifest}

def run_report_exports(root:Path):
    rows=[{"item_no":1,"price_code":"S-001","description":"بتن","quantity":12.5,"unit":"m3","unit_price":100,"total":1250,"source":"S1"}]
    summary={"cost":{"base":1250,"grand_total":1250,"line_count":1}}
    prepared=prepare_report(rows,"fa")
    out={}
    out["xlsx"]=export_xlsx(rows,root/"report.xlsx","گزارش متره",summary,{"revision":"R1"})
    out["pdf"]=export_pdf(rows,root/"report.pdf","گزارش متره",summary,{"revision":"R1"})
    out["docx"]=export_docx(rows,root/"report.docx","گزارش متره",summary,{"revision":"R1"})
    return {"files":{k:p.exists() and p.stat().st_size>0 for k,p in out.items()},"rtl_columns":list(prepared[0].keys()),"totals":totals(prepared)}

def run_revision():
    before=[{"object_id":"C1","quantity":10,"review_status":"approved"}]
    after=[{"object_id":"C1","quantity":12,"review_status":"approved"}]
    return build_impact_report(before,after,[{"id":"B1","quantity":10}],[{"id":"B1","quantity":12}],{"total":100},{"total":120})

def run_scale():
    project={"id":"P-SCALE","takeoffs":[{"id":str(i),"quantity":1,"source":"S"+str(i),"description":"x","unit":"m3"} for i in range(10000)]}
    snap=project_performance_snapshot(project)
    page=paginate(project["takeoffs"],page=100,page_size=100)
    return {"snapshot":snap,"page":page}

def run_release():
    version=load_version()
    info=ReleaseInfo("StructuralPro",version,"stable")
    hardening=run_hardening_checks()
    return {"version":version,"release":info.as_dict(),"hardening":hardening}

def run_all():
    with tempfile.TemporaryDirectory(prefix="sp_p111_p115_") as td:
        return {"P111":run_data_pack(),"P112":run_report_exports(Path(td)),"P113":run_revision(),"P114":run_scale(),"P115":run_release()}
