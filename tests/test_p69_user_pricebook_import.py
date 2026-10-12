from core.estimate.user_pricebook_import_v1 import *
def req(h="a"*64): return ImportRequest("abnieh.xlsx","xlsx",1404,"abnieh","user-upload",h)
def test_import():
    r=req(); out=finalize_import(r,100,r.sha256); assert out.row_count==100 and out.status=="needs_review"
def test_bad_hash():
    r=req()
    try: finalize_import(r,100,"b"*64)
    except ValueError: return
    assert False
def test_bad_format():
    r=ImportRequest("x.exe","exe",1404,"abnieh","user-upload","a"*64)
    try: validate_request(r)
    except ValueError: return
    assert False
