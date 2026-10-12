from core.acceptance.p116_p120 import run_all
def test_p116_p120_acceptance_all():
 r=run_all()
 assert r["P116"]["verified"] and r["P116"]["tamper_rejected"]
 assert r["P117"]["chain_valid"] and r["P117"]["count"]==2
 assert r["P118"]["restored"] and r["P118"]["manifest_ok"]
 assert r["P119"]["hits"]==1 and r["P119"]["deterministic"]
 assert r["P120"]["valid"] and r["P120"]["errors"]==[]
