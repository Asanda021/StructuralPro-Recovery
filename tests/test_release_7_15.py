from core.revisions.compare import compare_rows,summary
from core.takeoff.templates import TemplateLibrary
from core.takeoff.formulas import evaluate
from core.integrations.excel_bridge import export_rows,import_rows
from core.reports.designer import ReportLayout
from core.search.global_search import search_project
from core.history.undo import CommandStack
from core.drawings.sheets import SheetRegistry
from core.drawings.markup import Markup,MarkupStore
def test_revision_template_formula():
    c=compare_rows([{"price_code":"A","quantity":10,"total":100}], [{"price_code":"A","quantity":14,"total":140},{"price_code":"B","quantity":2,"total":20}])
    assert summary(c)["added"]==1 and summary(c)["changed"]==1 and summary(c)["quantity_delta"]==6
    assert TemplateLibrary().get("WALL-AREA").formula=="count * (length * height - openings)"
    assert evaluate("length*height-openings",{"length":5,"height":3,"openings":2})==13
def test_excel_layout_and_search(tmp_path):
    rows=[{"price_code":"A","description":"دیوار","quantity":2,"unit":"m2","unit_price":10,"total":20}]
    p=tmp_path/"x.xlsx"; export_rows(rows,p); assert import_rows(p)[0]["total"]==20
    assert ReportLayout().visible(rows[0])["description"]=="دیوار"
    assert search_project({"name":"پروژه تهران","takeoffs":[{"title":"دیوار","quantities":[{"title":"بلوک","price_code":"A"}]}]},"دیوار")
def test_undo_redo_sheets_markup():
    state=[]
    s=CommandStack()
    s.execute(lambda:state.append(1),lambda:state.pop())
    assert state==[1] and s.undo() and state==[] and s.redo() and state==[1]
    reg=SheetRegistry(); reg.add(id="A1",name="پلان طبقه اول",page=1,scale="1:100")
    assert reg.search("طبقه")[0].id=="A1"
    ms=MarkupStore(); ms.add(Markup("M1","text","یادداشت",page=1)); assert len(ms.for_page(1))==1
