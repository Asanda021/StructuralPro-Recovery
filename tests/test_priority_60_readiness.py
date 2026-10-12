from core.platform.readiness import run_readiness
def test_all_checks_required_for_ready():
 r=run_readiness([("db",lambda:True),("engine",lambda:True)])
 assert r.ready and not r.failures
def test_one_failure_makes_readiness_false():
 r=run_readiness([("db",lambda:True),("engine",lambda:False)])
 assert not r.ready and [x.name for x in r.failures]==["engine"]
def test_exception_is_fail_closed():
 r=run_readiness([("broken",lambda:1/0)])
 assert not r.ready and "ZeroDivisionError" in r.failures[0].detail
def test_results_are_deterministic_in_declared_order():
 r=run_readiness([("b",lambda:True),("a",lambda:True)])
 assert [x.name for x in r.checks]==["b","a"]
