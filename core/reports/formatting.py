"""RTL-safe report formatting primitives."""
from __future__ import annotations
import html
from .decimal_values import decimal_value
def rtl_text(value): return f"\u202B{value}\u202C"
def money(value, decimals=0):
    if not isinstance(decimals,int) or isinstance(decimals,bool) or decimals<0 or decimals>16:
        raise ValueError("invalid decimal places")
    amount=decimal_value(value,field="amount")
    return format(amount,f",.{decimals}f")
def table_html(headers, rows):
    h="".join(f"<th>{html.escape(str(x))}</th>" for x in headers)
    body="".join("<tr>"+"".join(f"<td>{html.escape(str(x))}</td>" for x in row)+"</tr>" for row in rows)
    return f'<table dir="rtl"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'
