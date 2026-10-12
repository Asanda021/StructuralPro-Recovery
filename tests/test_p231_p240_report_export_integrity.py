from core.reports.export_integrity_v1 import validate_rows,canonical_rows,fingerprint
import pytest
def row(): return {"ردیف":1,"کد":"A","شرح":"بتن","مقدار":2,"واحد":"m3"}
def test_valid(): assert not validate_rows([row()])
def test_missing_fails(): assert validate_rows([{"کد":"A"}])
def test_negative_fails(): assert validate_rows([{**row(),"مقدار":-1}])
def test_canonical_stable(): assert fingerprint([row()])==fingerprint([row()])
def test_invalid_boundary():
 with pytest.raises(ValueError): canonical_rows([{"کد":"A"}])