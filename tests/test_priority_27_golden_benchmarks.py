from core.benchmark.golden import GoldenCase,GoldenResult,acceptance_summary,default_cases,run_case

def test_golden_cases_are_explicit_and_nonempty():
    cases=default_cases()
    assert len(cases)>=3
    assert all(c.case_id and c.expected_keys for c in cases)

def test_golden_case_runner_reports_missing_contract_keys():
    case=GoldenCase("x","demo",("id","name"))
    result=run_case(case,lambda _: {"id":"1"})
    assert not result.passed and result.missing_keys==("name",)

def test_acceptance_summary_requires_all_cases_to_pass():
    results=[GoldenResult("a",True),GoldenResult("b",False)]
    summary=acceptance_summary(results)
    assert summary["passed"]==1 and summary["failed"]==1 and not summary["ready"]
