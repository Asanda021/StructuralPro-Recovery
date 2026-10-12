"""Professional report layout model: columns, grouping, totals, RTL and pagination."""
from dataclasses import dataclass,field
_FIELD_MAP={"ردیف":"item_no","کد":"price_code","شرح":"description","مقدار":"quantity","واحد":"unit","بهای واحد":"unit_price","مبلغ":"total","منبع":"source"}
@dataclass
class ReportLayout:
    title:str="گزارش متره و برآورد"; columns:list[str]=field(default_factory=lambda:["ردیف","کد","شرح","مقدار","واحد","بهای واحد","مبلغ"]); group_by:str=""; rtl:bool=True
    page_size:int=35; header:str=""; footer:str=""
    def visible(self,row):
        out={label:row.get(_FIELD_MAP.get(label,label),row.get(label,"")) for label in self.columns}
        for key in ("item_no","price_code","description","quantity","unit","unit_price","total","source"):
            out.setdefault(key,row.get(key,""))
        return out
    def reorder(self,columns): self.columns=list(columns); return self
    def render_rows(self,rows):
        rows=[self.visible(r) for r in rows]
        if not self.group_by: return rows
        key=self.group_by; out=[]; current=None; subtotal=0.0
        for r in rows:
            g=r.get(key,"")
            if current is not None and g!=current: out.append({key:f"جمع {current}","مبلغ":subtotal})
            if g!=current: current=g; subtotal=0.0
            try: subtotal+=float(r.get("مبلغ",0) or 0)
            except (TypeError,ValueError): pass
            out.append(r)
        if current is not None: out.append({key:f"جمع {current}","مبلغ":subtotal})
        return out
    def pages(self,rows): 
        rendered=self.render_rows(rows); return [rendered[i:i+self.page_size] for i in range(0,len(rendered),self.page_size)] or [[]]
