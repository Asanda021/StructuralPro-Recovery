"""Conservative RTL report metadata and column ordering."""
from __future__ import annotations
def report_schema(columns, language="fa", rtl=True, decimals=2, currency="IRR"):
    cols=[str(x) for x in columns]
    return {"language":language,"rtl":bool(rtl),"decimals":int(decimals),"currency":currency,"columns":cols}
