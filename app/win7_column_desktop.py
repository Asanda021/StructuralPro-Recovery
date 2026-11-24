"""Windows 7 SP1 compatibility candidate: Python 3.8 / Tcl-Tk GUI.

Deliberately avoids Qt6/Python3.12. Nonfinancial draft from real PDF vector
source; user-entered steel assumptions never become payable BOQ.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import traceback
from hashlib import sha256
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.drawings.pdf_column_length_schedule import draft_column_length_schedule
from core.drawings.pdf_column_weight_preview import (
    draft_component_weight_preview, export_weight_preview_xlsx,
)
from openpyxl import load_workbook


class ColumnWin7Window(object):
    def __init__(self, root):
        self.root = root
        self.root.title("StructuralPro - Column Takeoff (Windows 7)")
        self.root.geometry("940x660")
        self.root.minsize(680, 540)
        self.root.option_add("*Font", "Tahoma 9")
        self.path = tk.StringVar()
        self.profile_count = tk.StringVar(value="2")
        self.unit_mass = tk.StringVar(value="15.8")
        self.status = tk.StringVar(value="فایل PDF انتخاب نشده است.")
        self.schedule = None
        self.preview = None
        self.source_path = None
        frame = ttk.Frame(root, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="StructuralPro | متره آزمایشی ستون، Windows 7", font=("Tahoma", 13, "bold")).pack(anchor="e", pady=(0,8))
        ttk.Label(frame, text="این محاسبات فقط پیش‌نمایش‌اند. تأیید مهندسی، BOQ و صورت‌وضعیت نیستند.", foreground="#a02f2f").pack(anchor="e")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=10)
        ttk.Button(controls, text="انتخاب PDF", command=self.pick).pack(side="right", padx=5)
        ttk.Entry(controls, textvariable=self.path, state="readonly").pack(side="right", fill="x", expand=True, padx=5)
        ttk.Button(controls, text="۱. استخراج", command=self.extract).pack(side="right", padx=5)

        ttk.Label(frame, textvariable=self.status, wraplength=820, justify="right").pack(fill="x", pady=(0,8))
        cols = ("type", "count", "printed", "extended", "status")
        self.table = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        for key,title,width in [
            ("type","تیپ",110),("count","تعداد موقعیت",140),("printed","طول هر تیپ (m)",160),
            ("extended","جمع طول (m)",155),("status","وضعیت",260),
        ]:
            self.table.heading(key,text=title)
            self.table.column(key,width=width,anchor="center")
        self.table.pack(fill="both",expand=True)
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=12)
        ttk.Label(bottom, text="پروفیل برای هر ستون (فرض):").pack(side="right", padx=5)
        ttk.Entry(bottom, textvariable=self.profile_count, width=7).pack(side="right")
        ttk.Label(bottom, text="وزن واحد طول kg/m (فرض):").pack(side="right", padx=5)
        ttk.Entry(bottom, textvariable=self.unit_mass, width=10).pack(side="right")
        ttk.Button(bottom,text="۲. وزن فرضی",command=self.compute).pack(side="right",padx=7)
        ttk.Button(bottom,text="۳. ذخیره Excel",command=self.export).pack(side="left",padx=7)
        self.summary = tk.StringVar(value="ابتدا PDF را استخراج کنید.")
        ttk.Label(frame,textvariable=self.summary,font=("Tahoma",11,"bold")).pack(anchor="e")
        ttk.Label(frame,text="وابستگی به اینترنت ندارد | فایل PDF خصوصی در برنامه ذخیره نمی‌شود.",foreground="#666666").pack(anchor="e",pady=8)

    def _clear(self, note=None):
        self.schedule = None
        self.preview = None
        self.source_path = None
        for row in self.table.get_children():
            self.table.delete(row)
        self.summary.set("متره و وزن قبلی پاک شد.")
        self.status.set(note or "فایل جدید انتخاب شد. استخراج را اجرا کنید.")

    def pick(self):
        f = filedialog.askopenfilename(filetypes=[("PDF drawing","*.pdf")])
        if f:
            self.path.set(f)
            self._clear("PDF انتخاب شد: " + str(Path(f).name))

    def set_source(self, path):
        self.path.set(str(path))
        self._clear()

    def extract(self):
        self._clear("در حال استخراج...")
        self.root.update_idletasks()
        try:
            source = Path(self.path.get())
            if not source.is_file() or source.suffix.lower() != ".pdf":
                raise ValueError("فایل PDF معتبر انتخاب نشده است.")
            report = draft_column_length_schedule(source)
            if report.get("status") not in ("DRAFT_COMPLETE_GRID_EVIDENCE","PARTIAL_WITH_BLOCKED_GRID_NODES"):
                raise ValueError("در این نقشه شواهد کافی برای تیپ‌بندی ستون پیدا نشد: " + str(report.get("status")))
            if not report.get("groups"):
                raise ValueError("هیچ طولِ دارای شاهد کافی در نقشه یافت نشد.")
            self.schedule = report
            self.source_path = str(source)
            for group in report["groups"]:
                self.table.insert("",tk.END,values=(group["type_tag"],group["grid_location_candidates"],
                    group["printed_type_length_m"],group["draft_extended_length_m"],group["status"]))
            self.summary.set("طول آزمایشی کل: %s متر؛ %s موقعیت (%s مورد مسدود)" % (
                report["draft_extended_length_total_m"],report["grid_node_count"],report["blocked_node_count"]))
            self.status.set("شیت پلان: %s | شواهد PDF: %s | تأیید مالی: خیر" %
                            (report["plan_page"],report["document_sha256"][:16]))
        except Exception as exc:
            self.status.set("استخراج ناموفق: " + str(exc))
            self.summary.set("بدون مقدار قابل استفاده.")
            return False
        return True

    def _verify_pdf(self):
        if self.schedule is None or self.source_path is None or self.path.get() != self.source_path:
            raise ValueError("ابتدا فایل انتخاب‌شده را استخراج کنید.")
        if sha256(Path(self.source_path).read_bytes()).hexdigest()!=self.schedule["document_sha256"]:
            self._clear("فایل PDF بعد از استخراج تغییر کرده است.")
            raise ValueError("PDF تغییر کرده؛ استخراج دوباره لازم است.")

    def compute(self):
        try:
            self._verify_pdf()
            inputs = {g["type_tag"]: {
                "profile_name": "USER_ASSUMED",
                "profile_count": self.profile_count.get(),
                "profile_unit_mass_kg_m": self.unit_mass.get(),
                "plate_count": 0,
            } for g in self.schedule["groups"]}
            self.preview = draft_component_weight_preview(self.schedule,inputs)
            self.summary.set("طول آزمایشی: %s m | وزن فرضی فقط پروفیل: %s kg | ورق/اتصال: محاسبه‌نشده" %
                (self.schedule["draft_extended_length_total_m"],self.preview["draft_weight_total_kg"]))
            self.status.set("مبنای وزن، ورودی کاربر است؛ استخراج‌شده از نقشه یا تأیید مالی نیست.")
        except Exception as exc:
            self.preview = None
            self.status.set("محاسبه ناموفق: " + str(exc))
            return False
        return True

    def export(self, target=None):
        try:
            self._verify_pdf()
            if self.preview is None:
                raise ValueError("ابتدا وزن سناریویی را محاسبه کنید.")
            if target is None:
                target=filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")])
            if not target:
                return False
            export_weight_preview_xlsx(self.schedule,self.preview,target)
            self.status.set("Excel ذخیره شد: "+str(target))
            return True
        except Exception as exc:
            self.status.set("خروجی ناموفق: "+str(exc))
            return False


def _make_synthetic(path, first="3.5", second="6.25"):
    """Drawing generated at runtime, never hardcoded to the user's project."""
    import pymupdf
    from core.drawings.pdf_vector_type_labels import _C, _ONE, _TWO
    with pymupdf.open() as doc:
        plan=doc.new_page(width=722,height=547)
        plan.insert_text((38,45),"Column Type Plan")
        xs, ys=(105,253,420),(122,252,409)
        for x in xs:
            plan.draw_line((x,ys[0]),(x,ys[-1]))
        for y in ys:
            plan.draw_line((xs[0],y),(xs[-1],y))
        for level,y in enumerate(ys):
            for x in xs:
                plan.draw_rect((x-3,y-3,x+3,y+3))
                for template,gx,w in ((_C,x+8,6),
                                      (_ONE if level==0 else _TWO,x+17,1.5 if level==0 else 5.7)):
                    shape=plan.new_shape()
                    shape.draw_polyline([(gx+u*w,y+9+v*9) for u,v in template])
                    shape.finish(width=0.18,closePath=False)
                    shape.commit()
        details=doc.new_page(width=722,height=547)
        details.insert_text((38,45),"Column Details")
        details.insert_text((70,132),"C1 L="+first+" m")
        details.insert_text((70,270),"C2 L="+second+" m")
        doc.save(str(path))


def smoke(directory):
    dest=Path(directory)
    dest.mkdir(parents=True,exist_ok=True)
    result={"status":"FAIL","checks":{},"python":sys.version,"notes":"Windows 2022 smoke does not prove Windows 7 startup"}
    root=None
    try:
        root=tk.Tk()
        app=ColumnWin7Window(root)
        root.update()
        assert root.winfo_exists() and root.winfo_viewable()
        result["checks"]["window"]="PASS"
        first=dest/"نقشه-اول.pdf"
        second=dest/"نقشه-دوم.pdf"
        invalid=dest/"خراب.pdf"
        excel=dest/"متره-ستون.xlsx"
        _make_synthetic(first)
        _make_synthetic(second,"2.25","5")
        invalid.write_bytes(b"not-a-pdf")
        app.set_source(first)
        assert app.extract()
        assert app.schedule["grid_node_count"]==9
        expected=Decimal("3")*Decimal("3.5")+Decimal("6")*Decimal("6.25")
        assert Decimal(app.schedule["draft_extended_length_total_m"])==expected
        result["checks"]["vector_pdf"]="PASS"
        app.profile_count.set("3")
        app.unit_mass.set("8.25")
        assert app.compute()
        assert Decimal(app.preview["draft_weight_total_kg"])==expected*3*Decimal("8.25")
        result["checks"]["editable_weight"]="PASS"
        assert app.export(str(excel))
        book=load_workbook(excel,data_only=False)
        assert book["Preview"]["B11"].data_type=="f"
        assert book["Preview"]["B5"].value=="NO" and book["Preview"]["B6"].value=="NO"
        assert book["PDF positions"].max_row==10
        book.close()
        result["checks"]["xlsx_roundtrip"]="PASS"
        app.set_source(second)
        assert app.extract()
        assert Decimal(app.schedule["draft_extended_length_total_m"])==Decimal("3")*Decimal("2.25")+Decimal("6")*Decimal("5")
        app.set_source(invalid)
        assert not app.extract() and app.schedule is None
        result["checks"]["switch_and_invalid"]="PASS"
        result["status"]="PASS"
    except Exception:
        result["traceback"]=traceback.format_exc()
    finally:
        (dest/"win7-smoke.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        if root is not None:
            root.destroy()
    return 0 if result["status"]=="PASS" else 1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--smoke-test",metavar="DIR")
    parser.add_argument("source",nargs="?")
    args=parser.parse_args()
    if args.smoke_test:
        return smoke(args.smoke_test)
    root=tk.Tk()
    ui=ColumnWin7Window(root)
    if args.source:
        ui.set_source(args.source)
    root.mainloop()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
