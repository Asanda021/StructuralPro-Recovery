"""P86 canonical item-code normalization."""
import re
def normalize_item_code(value):
    if value is None: return ""
    s=str(value).strip()
    s="".join(chr(ord("0")+ord(c)-ord("0")) if "0"<=c<="9" else c for c in s)
    pers="۰۱۲۳۴۵۶۷۸۹"; arb="٠١٢٣٤٥٦٧٨٩"
    for i,c in enumerate(pers): s=s.replace(c,str(i))
    for i,c in enumerate(arb): s=s.replace(c,str(i))
    s=s.replace("–","-").replace("—","-").replace("−","-")
    s=re.sub(r"\s+","",s)
    s=re.sub(r"[^0-9A-Za-zآ-ی-]","",s)
    s=re.sub(r"-+","-",s).strip("-")
    return s
def code_key(item_code, unit):
    return normalize_item_code(item_code), str(unit or "").strip()
