from core.drawings.dwg_takeoff import DWGDocument,DWGEntity
from core.drawings.takeoff_rules import DrawingRuleEngine
from core.drawings.revisions import compare,quantity_delta
from core.ai.qa_engine import ProjectQA
from core.projects.statement_engine import StatementLine,build_statement
def test_stage4():
    doc=DWGDocument(entities=[DWGEntity("LINE","WALL","1",{"length":5}),DWGEntity("LINE","WALL","2",{"length":7})],layers=["WALL"])
    rows=DrawingRuleEngine.from_layer_map({"WALL":{"metric":"length","unit":"m","description":"دیوار","price_code":"0101"}}).apply(doc)
    assert rows[0]["quantity"]==12
    diff=compare([{"handle":"1","x":1}],[{"handle":"1","x":2},{"handle":"2"}])
    assert diff["summary"]=={"added":1,"removed":0,"changed":1,"unchanged":0}
    assert quantity_delta([{"description":"دیوار","unit":"m","quantity":10}],[{"description":"دیوار","unit":"m","quantity":13}])[0]["delta"]==3
def test_stage5():
    issues=ProjectQA().run({"name":"P","takeoffs":[{"quantity":-1,"unit":"","price_code":""}]})
    assert {x["code"] for x in issues}=={"negative_quantity","missing_unit","missing_price_code"}
def test_stage6():
    result=build_statement([StatementLine("0101","بتن","m3",100,200,10,5)],retention_rate=.1,advance_recovery_rate=.05,other_deduction_rate=.02,advance_paid=1000)
    assert result["gross_current"]==2000 and result["retention"]==200 and result["advance_recovery"]==100 and result["payable"]==1660
