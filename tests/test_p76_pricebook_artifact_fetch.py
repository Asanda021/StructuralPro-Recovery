from core.estimate.pricebook_artifact_fetch_v1 import ARTIFACTS_1404, manifest

def test_four_1404_artifacts_have_direct_download_targets():
    assert len(ARTIFACTS_1404)==4
    assert all(x.url.startswith("https://drive.google.com/uc?export=download&id=") for x in ARTIFACTS_1404)
    assert {x.discipline for x in ARTIFACTS_1404}=={"ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی"}
