"""Professional offline report exporters with RTL-aware Excel/PDF output."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import re
from xml.sax.saxutils import escape


from decimal import Decimal, InvalidOperation, localcontext
from datetime import datetime
import math

REPORT_FONT = 'Arial' if __import__('os').name == 'nt' else 'DejaVu Sans'
FA_LABELS = {
 'item_no':'ردیف','item_code':'کد آیتم','price_code':'کد قیمت','chapter':'فصل',
 'category':'دسته','group':'گروه','description':'شرح','quantity':'مقدار','unit':'واحد',
 'unit_price':'بهای واحد','total':'مبلغ','status':'وضعیت','source_id':'منبع متره',
 'notes':'یادداشت','code':'کد','source':'منبع','component':'جزء','field':'عنوان',
 'value':'مقدار و مرجع','project_id':'شناسه پروژه','project_name':'نام پروژه',
 'source_sha256':'هش مدرک اصلی','revision':'نسخه','floor':'طبقه','member':'عضو',
 'formula':'فرمول','section':'بخش','row':'ردیف','created_by':'تهیه‌کننده',
 'reviewer':'بازبین','date':'تاریخ','currency':'واحد پول','id':'شناسه',
 'amendments':'اصلاحیه‌ها','references':'منابع','location':'موقعیت','building_id':'ساختمان',
}
FA_UNITS={'m':'متر','m2':'متر مربع','m3':'متر مکعب','kg':'کیلوگرم','ton':'تن',
 'mm':'میلی‌متر','cm':'سانتی‌متر','kg/m':'کیلوگرم بر متر','kg/m3':'کیلوگرم بر متر مکعب','IRR':'ریال'}
NUMBER_KEYS={'item_no','quantity','unit_price','total','amount','مقدار','مبلغ','بهای واحد','count','revision','مقدار دقیق','جمع دقیق','جمع','پیش از کسر','خالص','کسر مؤثر','مقدار پیشنهادی','نسخه مبنا'}

def report_date(on=None):
    """Jalali date from the actual host date; no guessed project dates."""
    from PySide6.QtCore import QCalendar,QDate
    on=on or datetime.now().astimezone().date()
    parts=QCalendar(QCalendar.Jalali).partsFromDate(QDate(on.year,on.month,on.day))
    return f'{parts.year:04}/{parts.month:02}/{parts.day:02}'.translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))

def _label(key):
    value=str(key)
    return FA_LABELS.get(value, FA_LABELS.get(value.casefold().replace(' ','_'), 'اطلاعات تکمیلی' if re.search('[A-Za-z]',value) else value))

def _report_metadata(title,metadata,columns=None):
    result={'نام گزارش':title,'تاریخ صدور شمسی':report_date()}
    for key,value in (metadata or {}).items():
        label=_label(key)
        # Unknown user-defined metadata is retained verbatim as a value, never lost.
        if label=='اطلاعات تکمیلی':value=str(key)+' : '+str(value)
        result[label if label not in result else label+' '+str(len(result))]=value
    for key,label in columns or []:
        if label.startswith('اطلاعات تکمیلی '):result['شناسه فنی ستون '+label]=key
    return result

def _technical_text(value):
    # File paths, URIs and colon-prefixed document IDs keep their logical LTR
    # order even when a Persian path component follows the identifier.
    return _cell(value).startswith(('/',chr(92))) or bool(re.match(r'^(?:[A-Za-z][A-Za-z0-9_.-]*:|[A-Za-z0-9_.-]+[/\\])',_cell(value)))


def _printed_value(row,key):
    value=_display_value(row,key)
    if key in ('unit','واحد','currency'):return FA_UNITS.get(str(value),value)
    return value

def excel_number(value):
    """Exact JSON/Excel boundary: <=15 significant decimal digits, round trip safe.

    Returns None for text/identity/overprecision. Never silently rounds a quantity.
    """
    if type(value) is bool or value is None:return None
    if not isinstance(value,(str,int,float,Decimal)):return None
    text=str(value)
    if not re.fullmatch(r'[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|[+-]?\.[0-9]+',text):return None
    try:d=Decimal(text)
    except InvalidOperation:return None
    if not d.is_finite():raise ValueError('عدد گزارش باید متناهی باشد')
    digits=list(d.as_tuple().digits)
    while len(digits)>1 and digits[-1]==0:digits.pop()
    if len(digits)>15:return None
    n=int(d) if d==d.to_integral_value() and abs(d)<10**15 else float(d)
    if not math.isfinite(float(n)) or Decimal(str(n))!=d:return None
    if n and (abs(n)<__import__('sys').float_info.min or abs(n)>1e307):return None
    return n

def _numeric_field(key,row):
    if key in NUMBER_KEYS:return True
    if key=='value':
        label=str(row.get('field',''))
        if any(x in label for x in ('منبع','شناسه','مرجع','هش','مسیر','فرمول','بازبین')):return False
        return any(x in label for x in ('مقدار','تعداد','وزن','طول','قطر','حجم','مساحت','مبلغ','نسخه','ضریب','فاصله','گام','عمق','ارتفاع','عرض','ضخامت','جمع','کسور','اختلاف'))
    return False

def write_excel_cell(cell,value,*,numeric=False,formula=False):
    if formula:
        cell.value=value;cell.data_type='f';return
    if isinstance(value,float) and not math.isfinite(value) or isinstance(value,Decimal) and not value.is_finite():
        raise ValueError('عدد گزارش باید متناهی باشد')
    number=excel_number(value) if numeric else None
    cell.value=number if number is not None else _cell(value)
    cell.data_type='n' if number is not None else 's'
    if number is not None:
        d=Decimal(str(value));scale=max(0,-d.as_tuple().exponent)
        cell.number_format='0.##############E+00' if number and (scale>15 or abs(number)>=10**15) else '#,##0'+('.'+'0'*scale if scale else '')

def style_workbook(book,title):
    """Shared style/print setup, without coercing existing formulas or text."""
    from openpyxl.styles import Font,Alignment,PatternFill,Border,Side
    from openpyxl.workbook.properties import CalcProperties
    from openpyxl.worksheet.pagebreak import Break
    for sheet in book:
        sheet.sheet_view.rightToLeft=True;sheet.print_options.horizontalCentered=True
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
        sheet.print_area=sheet.dimensions
        sheet.oddHeader.right.text=str(title).replace('&','&&');sheet.oddHeader.right.font=REPORT_FONT
        sheet.oddFooter.center.text='صفحه &P از &N';sheet.oddFooter.right.text=report_date()
        for row in sheet:
            for cell in row:
                # Pure identifiers stay LTR. Persian paragraphs remain logical Unicode.
                direction=2 if re.search(r'[\u0600-\u06ff]',str(cell.value or '')) and not _technical_text(cell.value) else 1
                cell.font=Font(name=REPORT_FONT,size=(cell.font.sz or 10) if cell.font.bold else 10,bold=cell.font.bold,color='17263B')
                cell.alignment=Alignment(horizontal='right',readingOrder=direction,vertical='top',wrap_text=True)
        if not sheet.print_title_rows:sheet.print_title_rows='1:1'
    book.calculation=CalcProperties(fullCalcOnLoad=True,forceFullCalc=True,calcMode='auto')


def _summary_items(summary):
    summary = summary or {}
    cost = summary.get("cost", summary) if isinstance(summary, dict) else {}
    items = []
    labels = (("base", "مبلغ پایه"), ("grand_total", "مبلغ نهایی"), ("line_count", "تعداد ردیف"),
              ("active_line_count", "ردیف‌های فعال"))
    for key, label in labels:
        if key in cost:
            items.append((label, cost.get(key)))
    for name, value in (cost.get("factors", {}) or {}).items():
        items.append((str(name), value))
    for name, value in (summary.get("amount_by_group", {}) or {}).items():
        items.append((f"گروه: {name}", value))
    statement = summary.get("statement", {}) if isinstance(summary, dict) else {}
    statement_labels = (
        ("gross_current", "مبلغ ناخالص این دوره"), ("retention", "کسور تضمین"),
        ("advance_recovery", "استهلاک پیش‌پرداخت"), ("taxable_current", "مبلغ مشمول مالیات"),
        ("tax", "مالیات"), ("insurance", "بیمه"), ("payable_current", "قابل پرداخت این دوره"),
        ("previous_paid", "پرداختی قبلی"), ("balance_after_current", "مانده پس از این دوره"),
    )
    for key, label in statement_labels:
        if key in statement:
            items.append((label, statement.get(key)))
    if "period_no" in summary:
        items.insert(0, ("شماره صورت‌وضعیت", summary["period_no"]))
    return items


def _columns(rows, columns=None):
    rows=list(rows)
    original=list(columns) if columns else [(key,key) for key in dict.fromkeys(key for row in rows for key in row)]
    if not original:return [('description','شرح')]
    return [(key,(_label(label) if _label(label)!='اطلاعات تکمیلی' else 'اطلاعات تکمیلی '+str(i))) for i,(key,label) in enumerate(original,1)]


def _cell(value):
    if value is None:
        return ""
    return str(value)


def _display_value(row, key):
    value = row.get(key, "")
    if key == "status":
        return {"active": "فعال", "cancelled": "لغوشده"}.get(str(value), value)
    return value


def export_csv(rows, path, title="گزارش استراکچرال پرو", summary=None, metadata=None, columns=None):
    import csv
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _columns(rows, columns)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv_writer = csv.writer(f)
        def safe(value):
            text=_cell(value)
            # CSV carries no cell types. Neutralize formula triggers while retaining
            # canonical negative numbers and preserving original content after prefix.
            if text.lstrip().startswith(('=','+','-','@','\t','\r','\n')) and not (text.startswith('-') and excel_number(text) is not None):return "'"+text
            return text
        class SafeWriter:
            def writerow(self,values):csv_writer.writerow([safe(v) for v in values])
            def writerows(self,records):
                for values in records:self.writerow(values)
        w=SafeWriter()
        w.writerow([title])
        w.writerow(["CSV داده متنی است؛ چیدمان، فونت و راست‌به‌چپ دیداری در این قالب ذخیره نمی‌شود."])
        for key,value in _report_metadata(title,metadata,cols).items():
            w.writerow([key,value])
        w.writerow([])
        w.writerow([label for _, label in cols])
        w.writerows([_cell(_display_value(row, key)) for key, _ in cols] for row in rows)
    return path


def export_xlsx(rows, path, title="گزارش استراکچرال پرو", summary=None, metadata=None, columns=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _columns(rows, columns)
    wb = Workbook()
    detail = wb.active
    detail.title = "ریز متره"
    detail.sheet_view.rightToLeft = True
    summary_ws = wb.create_sheet("خلاصه")
    summary_ws.sheet_view.rightToLeft = True
    info_ws = wb.create_sheet("اطلاعات")
    info_ws.sheet_view.rightToLeft = True

    detail.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(cols)))
    write_excel_cell(detail.cell(1,1),title)
    detail.cell(1, 1).font = Font(bold=True, size=16)
    detail.cell(1, 1).alignment = Alignment(horizontal="right", readingOrder=2)
    detail.append([])
    detail.merge_cells(start_row=3,start_column=1,end_row=3,end_column=max(1,len(cols)))
    detail.cell(3, 1, "خلاصه تجاری")
    detail.cell(3, 1).font = Font(bold=True)
    detail.cell(3, 1).alignment = Alignment(horizontal="right", readingOrder=2)
    summary_items = _summary_items(summary)
    for i, (label, value) in enumerate(summary_items, 4):
        # Ordinal/code columns can be very narrow. Give summary prose the
        # combined label span and leave the last column for exact quantities.
        value_col=max(2,len(cols))
        if value_col>2:detail.merge_cells(start_row=i,start_column=1,end_row=i,end_column=value_col-1)
        write_excel_cell(detail.cell(i,1),label)
        write_excel_cell(detail.cell(i,value_col),value,numeric=True)
    header_row = max(6, 4 + len(summary_items))
    detail.merge_cells(start_row=header_row,start_column=1,end_row=header_row,end_column=max(1,len(cols)))
    detail.cell(header_row, 1, "ریز متره و برآورد")
    detail.cell(header_row, 1).font = Font(bold=True)
    header_row += 1
    for col,(_,label) in enumerate(cols,1):write_excel_cell(detail.cell(header_row,col),label)
    column_positions={key:i+1 for i,(key,_) in enumerate(cols)}
    for index,row in enumerate(rows,header_row+1):
        for col,(key,_) in enumerate(cols,1):
            write_excel_cell(detail.cell(index,col),_display_value(row,key),numeric=_numeric_field(key,row))
        if all(k in column_positions and row.get(k) is not None for k in ('quantity','unit_price','total')):
            q,p,t=(excel_number(row[k]) for k in ('quantity','unit_price','total'))
            if all(v is not None for v in (q,p,t)):
                with localcontext() as context:
                    context.prec=512
                    matches=Decimal(str(row['quantity']))*Decimal(str(row['unit_price']))==Decimal(str(row['total']))
                if matches:
                    scale=max(0,-Decimal(str(row['total'])).as_tuple().exponent)
                    formula=f"=ROUND({get_column_letter(column_positions['quantity'])}{index}*{get_column_letter(column_positions['unit_price'])}{index},{scale})"
                    write_excel_cell(detail.cell(index,column_positions['total']),formula,formula=True)
    thin = Side(style="thin")
    for cell in detail[header_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="right", readingOrder=2, vertical="top", wrap_text=True)
        cell.border = Border(bottom=thin)
    for row in detail.iter_rows(min_row=header_row + 1):
        for cell in row:
            cell.alignment = Alignment(horizontal="right", readingOrder=2, vertical="top", wrap_text=True)
    detail.freeze_panes = f"A{header_row + 1}"
    detail.auto_filter.ref = f"A{header_row}:{get_column_letter(max(1, len(cols)))}{detail.max_row}"
    for idx, (key, label) in enumerate(cols, 1):
        width = max(12, min(42, max([len(str(label))] + [len(_cell(r.get(key))) for r in rows]) + 2))
        detail.column_dimensions[get_column_letter(idx)].width = width

    write_excel_cell(summary_ws["A1"],title)
    summary_ws["A1"].font = Font(bold=True, size=16)
    summary_ws["A3"], summary_ws["B3"] = "شرح", "مقدار"
    for i, (label, value) in enumerate(_summary_items(summary), 4):
        write_excel_cell(summary_ws.cell(i,1),label)
        write_excel_cell(summary_ws.cell(i,2),value,numeric=True)
    for cell in summary_ws[3]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="right", readingOrder=2)
    for row in summary_ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(horizontal="right", readingOrder=2, vertical="top", wrap_text=True)
    summary_ws.column_dimensions["A"].width = 32
    summary_ws.column_dimensions["B"].width = 24

    info_ws["A1"], info_ws["B1"] = "فیلد", "مقدار"
    info_ws["A1"].font = info_ws["B1"].font = Font(bold=True)
    info_ws["A2"]="نام گزارش"
    write_excel_cell(info_ws["B2"],title)
    for i, (key, value) in enumerate(_report_metadata(title,metadata,cols).items(), 3):
        write_excel_cell(info_ws.cell(i,1),key)
        write_excel_cell(info_ws.cell(i,2),value)
    for row in info_ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(horizontal="right", readingOrder=2, wrap_text=True)
    info_ws.column_dimensions["A"].width = 28
    info_ws.column_dimensions["B"].width = 48
    detail.print_title_rows=f"{header_row}:{header_row}"
    style_workbook(wb,title)
    wb.save(path)
    return path


def export_docx(rows, path, title="گزارش استراکچرال پرو", summary=None, metadata=None, columns=None, *, landscape=False):
    from docx import Document
    from docx.enum.table import WD_TABLE_DIRECTION,WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_ORIENT
    from docx.shared import Inches,Pt,RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rows=list(rows);cols=_columns(rows,columns);d=Document()
    normal=d.styles['Normal'];normal.font.name=REPORT_FONT;normal.font.size=Pt(10)
    for name in ('Normal','Title','Heading 1','Heading 2'):
        style=d.styles[name];style.font.name=REPORT_FONT;style.font.color.rgb=RGBColor(0,0,0)
        fonts=style.element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ('ascii','hAnsi','cs','eastAsia'):fonts.set(qn('w:'+attr),REPORT_FONT)
        lang=OxmlElement('w:lang');lang.set(qn('w:val'),'fa-IR');lang.set(qn('w:bidi'),'fa-IR');style.element.get_or_add_rPr().append(lang)
    section=d.sections[0];section.left_margin=section.right_margin=Inches(.6)
    if landscape or len(cols)>6:section.orientation=WD_ORIENT.LANDSCAPE;section.page_width,section.page_height=section.page_height,section.page_width
    def write(paragraph,value,technical=False):
        technical=technical or _technical_text(value)
        paragraph.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        ppr=paragraph._p.get_or_add_pPr()
        if ppr.find(qn('w:bidi')) is None:
            bidi=OxmlElement('w:bidi');bidi.set(qn('w:val'),'0' if technical else '1');ppr.insert_element_before(bidi,'w:jc')
        # Logical start is the right edge for RTL paragraphs in OOXML.
        # Physical 'right' was mirrored to the left by LibreOffice.
        if not technical:ppr.find(qn('w:jc')).set(qn('w:val'),'start')
        text=_cell(value)
        parts=[text] if technical else re.split(r'([A-Za-z][A-Za-z0-9_:/\\.\-+()=]*)',text)
        for part in parts:
            if not part:continue
            run=paragraph.add_run(part);run.font.name=REPORT_FONT
            rpr=run._r.get_or_add_rPr();fonts=rpr.get_or_add_rFonts();fonts.set(qn('w:cs'),REPORT_FONT)
            rtl=OxmlElement('w:rtl');rtl.set(qn('w:val'),'0' if technical or not _PERSIAN_TEXT.search(part) else '1');rpr.append(rtl)
    def heading(text,level=1):write(d.add_heading('',level),text)
    def table(headers,data,widths=None):
        t=d.add_table(rows=1,cols=len(headers));t.table_direction=WD_TABLE_DIRECTION.RTL;t.alignment=WD_TABLE_ALIGNMENT.RIGHT;t.style='Light Shading Accent 1';t.autofit=False
        available=(section.page_width-section.left_margin-section.right_margin)/12700
        widths=widths or ([available*.35,available*.65] if len(headers)==2 else [available/len(headers)]*len(headers))
        for i,width in enumerate(widths):t.columns[i].width=Pt(width)
        for i,label in enumerate(headers):
            t.rows[0].cells[i].width=Pt(widths[i]);write(t.rows[0].cells[i].paragraphs[0],label)
        repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for record in data:
            cells=t.add_row().cells
            for i,value in enumerate(record):
                technical=not _PERSIAN_TEXT.search(_cell(value)) or headers[i] in ('منبع','منبع متره','کد','کد آیتم','کد قیمت')
                cells[i].width=Pt(widths[i]);write(cells[i].paragraphs[0],value,technical)
        # A paragraph between tables avoids inherited table nesting/spacing.
        borders=OxmlElement('w:tblBorders')
        for side in ('top','left','bottom','right','insideH','insideV'):
            item=OxmlElement('w:'+side);item.set(qn('w:val'),'single');item.set(qn('w:sz'),'4');item.set(qn('w:color'),'D9D9D9');borders.append(item)
        t._tbl.tblPr.append(borders)
        return t
    write(section.header.paragraphs[0],title)
    footer=section.footer.paragraphs[0];write(footer,'صفحه ')
    for code in ('PAGE','NUMPAGES'):
        if code=='NUMPAGES':write(footer,' از ')
        field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),code);footer._p.append(field)
    heading(title,0);heading('مشخصات پروژه و گزارش')
    table(['عنوان','مقدار'],list(_report_metadata(title,metadata,cols).items()))
    heading('جمع‌بندی')
    summary_rows=_summary_items(summary)
    if summary_rows:table(['شرح','مقدار'],summary_rows)
    else:write(d.add_paragraph(),'تعداد ردیف‌های گزارش: '+str(len(rows)))
    d.add_page_break();heading('ریزمتره و محاسبات')
    detail_rows,detail_cols=_pdf_identity(rows,cols)
    available=(section.page_width-section.left_margin-section.right_margin)/12700
    plan=_pdf_column_plan(detail_cols,detail_rows,font=_pdf_font(),usable_width=available)
    for panel_no,panel in enumerate(plan,1):
        if len(plan)>1:heading('ریزمتره بخش '+str(panel_no),2)
        total_width=sum(width for _,_,width in panel)
        table([label for _,label,_ in panel],[[_printed_value(row,key) for key,_,_ in panel] for row in detail_rows],widths=[width*available/total_width for _,_,width in panel])
    provenance=[]
    for row in rows:
        for key in ('source_id','source','notes','references','amendments'):
            if row.get(key) not in (None,''):provenance.append((_label(key),_cell(row[key])))
        if str(row.get('component','')).startswith(('اصلاحیه','هویت و منشأ')):
            provenance.append((_cell(row.get('field','عنوان')),_cell(row.get('value',''))))
    if provenance:
        heading('منابع و اصلاحیه‌ها');table(['عنوان','مدرک و توضیح'],provenance)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);d.save(path);return path


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("StructuralProUnicode", candidate))
                return "StructuralProUnicode"
            except Exception:
                pass
    raise RuntimeError("فونت Unicode فارسی برای خروجی PDF در دسترس نیست")


_PERSIAN_TEXT = re.compile(r"[\u0600-\u06ff]")
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _pdf_text(value):
    """Return safe, visually ordered Persian text for ReportLab paragraphs."""
    text = _cell(value)
    if _PERSIAN_TEXT.search(text):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
        except ImportError as exc:
            raise RuntimeError(
                "موتور شکل‌دهی و راست‌به‌چپ فارسی برای خروجی PDF نصب نیست"
            ) from exc
        text = get_display(arabic_reshaper.reshape(text), base_dir="R")
    return escape(text)


def _pdf_paragraph(value,style,width):
    """Wrap logical Persian lines before shaping; never reverse wrapped line order."""
    from reportlab.platypus import Paragraph
    from reportlab.pdfbase import pdfmetrics
    text=_cell(value)
    if _technical_text(text) and _PERSIAN_TEXT.search(text):
        from bidi.algorithm import get_display
        import arabic_reshaper
        return Paragraph(escape(get_display(arabic_reshaper.reshape(text),base_dir='L')),style)
    if not _PERSIAN_TEXT.search(text):return Paragraph(_pdf_text(text),style)
    output=[]
    for paragraph in text.splitlines() or ['']:
        current=''
        for word in paragraph.split(' '):
            candidate=(current+' '+word).strip()
            # Measure the actual shaped string, before XML escaping.
            from bidi.algorithm import get_display
            import arabic_reshaper
            shaped=get_display(arabic_reshaper.reshape(candidate),base_dir='R')
            if current and pdfmetrics.stringWidth(shaped,style.fontName,style.fontSize)>width:
                output.append(_pdf_text(current));current=word
            else:current=candidate
        output.append(_pdf_text(current))
    return Paragraph('<br/>'.join(output),style)


def _pdf_page_footer(canvas, doc, font, title="گزارش استراکچرال پرو"):
    canvas.saveState()
    canvas.setFont(font, 8)
    label = f"صفحه {doc.page}".translate(_PERSIAN_DIGITS)
    from html import unescape
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 16, unescape(_pdf_text(label)))
    canvas.drawString(doc.leftMargin,16,unescape(_pdf_text(report_date())))
    from reportlab.pdfbase import pdfmetrics
    header=str(title)
    while header and pdfmetrics.stringWidth(unescape(_pdf_text(header)),font,8)>doc.width:
        header=header[:-1]
    canvas.drawRightString(doc.pagesize[0]-doc.rightMargin,doc.pagesize[1]-14,unescape(_pdf_text(header)))
    canvas.restoreState()



def _pdf_column_plan(cols, rows, *, font, usable_width):
    """Size columns for printable numbers and split over-wide reports by field.

    Every original field is retained; the stable row identifier is repeated on
    continuation panels. No financial or engineering number is rounded or clipped.
    """
    from reportlab.pdfbase import pdfmetrics

    if not cols:
        return [[("description", "شرح", usable_width)]]
    if usable_width <= 100:
        raise ValueError("عرض قابل چاپ برای جدول PDF کافی نیست")
    anchor = next((key for key, _ in cols if key in
                   ("item_no", "ردیف", "id", "شناسه", "item_code", "price_code", "code", "کد", "source_id", "_pdf_row_id")), None)
    widths = {}
    for key, label in cols:
        values = [_display_value(row, key) for row in rows]
        numeric = bool(values) and all(_pdf_is_number(v) or v in (None, "") for v in values)
        numeric_values = [v for v in values if _pdf_is_number(v)]
        numeric_width = max((pdfmetrics.stringWidth(_pdf_text(v), font, 8)
                             for v in numeric_values), default=0) + 18
        label_width = pdfmetrics.stringWidth(_pdf_text(label), font, 8) + 17
        if numeric:
            # Numeric cells must not soft-wrap into misleading digit fragments.
            value_width = max((pdfmetrics.stringWidth(_pdf_text(v), font, 8)
                               for v in values), default=0) + 18
            width = max(49, label_width, value_width)
        else:
            # Long prose wraps at words, but no arbitrary fixed minimum 1/N.
            preferred = 150 if key in ("description", "شرح", "notes") else (96 if key == "source_id" else 68)
            width = max(54, preferred, label_width)
            # A detail column mixes source labels with exact engineering numbers.
            # Its numeric cells still use the non-wrapping numeric paragraph.
            if numeric_values:
                width = max(width, numeric_width)
        if width > usable_width - 12:
            if numeric_values:
                raise ValueError("عدد مالی یا مهندسی برای عرض صفحه PDF بیش از حد طولانی است")
            width = usable_width - 12
        widths[key] = width
    anchor_col = next(((key, label) for key, label in cols if key == anchor), None)
    remaining = [col for col in cols if col[0] != anchor] if anchor_col else cols
    panels = []
    current = [anchor_col] if anchor_col else []
    occupied = widths[anchor] if anchor_col else 0
    for key, label in remaining:
        width = widths[key]
        if current and occupied + width > usable_width:
            if anchor_col and len(current) == 1:
                raise ValueError("جدول گزارش PDF: ستون داده در کنار شناسه ردیف جا نمی‌شود")
            panels.append(current)
            current = [anchor_col] if anchor_col else []
            occupied = widths[anchor] if anchor_col else 0
        if occupied + width > usable_width:
            raise ValueError("جدول گزارش PDF: عرض ستون از محدوده صفحه بیشتر است")
        current.append((key, label))
        occupied += width
    if current:
        panels.append(current)
    return [[(key, label, widths[key]) for key, label in panel] for panel in panels]


def _pdf_is_number(value):
    """Treat numeric strings as numeric for layout without changing their text."""
    from decimal import Decimal
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[+-]?[0-9۰-۹٠-٩]+(?:[.,٬][0-9۰-۹٠-٩]+)*(?:[eE][+-]?[0-9۰-۹٠-٩]+)?", value.strip()))


def _pdf_identity(rows, cols):
    candidates=("item_no", "ردیف", "id", "شناسه", "item_code", "price_code", "code", "کد", "source_id")
    for key, _ in cols:
        if key in candidates:
            values=[str(row.get(key, "")).strip() for row in rows]
            if values and all(values) and len(set(values))==len(values):
                return rows, [(key, dict(cols)[key]), *[(k, label) for k, label in cols if k != key]]
    if not rows:
        return rows, cols
    key="_pdf_row_id"
    while any(key in row for row in rows) or any(k==key for k,_ in cols):
        key+="_"
    # The ordinal is report metadata, not an inferred engineering quantity.
    copies=[{**row, "_pdf_row_id": index} for index,row in enumerate(rows,1)]
    if key!="_pdf_row_id":
        raise ValueError("شناسه داخلی ردیف گزارش با داده ورودی تداخل دارد")
    return copies, [(key,"شناسه ردیف گزارش"), *cols]


def export_pdf(rows, path, title="گزارش استراکچرال پرو", summary=None, metadata=None, columns=None, fill_width=True):
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _columns(rows, columns)
    rows, cols = _pdf_identity(rows, cols)
    font = _pdf_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle("StructuralProBody", parent=styles["BodyText"], fontName=font,
                          alignment=TA_RIGHT, leading=13, fontSize=8)
    heading = ParagraphStyle("StructuralProHeading", parent=styles["Heading2"], fontName=font,
                             alignment=TA_RIGHT)
    title_style = ParagraphStyle("StructuralProTitle", parent=styles["Title"], fontName=font,
                                 alignment=TA_RIGHT)
    # Landscape keeps professional BOQ tables readable while remaining printable on A4.
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            rightMargin=24, leftMargin=24, topMargin=38, bottomMargin=34)
    story=[Paragraph(_pdf_text(title),title_style),Spacer(1,16),Paragraph(_pdf_text('مشخصات پروژه و گزارش'),heading)]
    metadata_rows=_report_metadata(title,metadata,cols)
    cover_data=[[_pdf_paragraph(value,body,doc.width*.65-12),_pdf_paragraph(label,body,doc.width*.35-12)] for label,value in metadata_rows.items()]
    cover=Table(cover_data,colWidths=[doc.width*.65,doc.width*.35],hAlign='RIGHT')
    cover.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.extend([cover,Spacer(1,16),Paragraph(_pdf_text('جمع‌بندی'),ParagraphStyle('StructuralProSummaryHeading',parent=heading,keepWithNext=True))])
    usable_width = doc.width
    numeric_body = ParagraphStyle("StructuralProNumbers", parent=body,
                                  splitLongWords=0, wordWrap=None)
    summary_rows = _summary_items(summary)
    if summary_rows:
        # RTL: labels appear on the right, values on the left.
        data = [[Paragraph(_pdf_text("مقدار"), body), Paragraph(_pdf_text("شرح"), body)]]
        from reportlab.pdfbase import pdfmetrics
        number_width=max([usable_width*.36]+[
            pdfmetrics.stringWidth(_pdf_text(value),font,8)+18
            for _,value in summary_rows if _pdf_is_number(value)])
        if number_width > usable_width-100:
            raise ValueError("عدد مالی خلاصه برای عرض صفحه PDF بیش از حد طولانی است")
        data += [[Paragraph(_pdf_text(b), numeric_body if _pdf_is_number(b) else body),
                  Paragraph(_pdf_text(a), body)] for a, b in summary_rows]
        table = Table(data, colWidths=[number_width, usable_width-number_width], repeatRows=1)
        table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .4, colors.grey),
                                   ("ALIGN", (0,0), (-1,-1), "RIGHT"),
                                   ("VALIGN", (0,0), (-1,-1), "TOP")]))
        story += [table, Spacer(1, 12)]
    from reportlab.platypus import LongTable, PageBreak
    plan = _pdf_column_plan(cols, rows, font=font, usable_width=usable_width)
    if fill_width:
        plan=[[(key,label,width*usable_width/sum(w for _,_,w in panel)) for key,label,width in panel] for panel in plan]
    for panel_no, panel in enumerate(plan, 1):
        if panel_no > 1:
            story.append(PageBreak())
        caption = "ریز متره و برآورد" if len(plan) == 1 else (
            f"ریز متره و برآورد — بخش {panel_no} از {len(plan)}")
        story.append(Paragraph(_pdf_text(caption), heading))
        # Reverse visual order in ReportLab's left-to-right table coordinates.
        panel = list(reversed(panel))
        data = [[_pdf_paragraph(label,body,width-10) for _,label,width in panel]]
        for row in rows:
            data.append([
                _pdf_paragraph(_printed_value(row,key),numeric_body if _pdf_is_number(_printed_value(row,key)) else body,width-10)
                for key,_,width in panel
            ])
        if not rows:
            data.append([Paragraph(_pdf_text("ردیفی برای نمایش وجود ندارد"), body)] +
                        [""] * (len(panel) - 1))
        table = LongTable(data, colWidths=[width for _, _, width in panel], repeatRows=1,
                          hAlign="RIGHT")
        table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), .35, colors.grey),
                                   ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                                   ("ALIGN", (0,0), (-1,-1), "RIGHT"),
                                   ("VALIGN", (0,0), (-1,-1), "TOP"),
                                   ("LEFTPADDING", (0,0), (-1,-1), 5),
                                   ("RIGHTPADDING", (0,0), (-1,-1), 5)]))
        story.append(table)
    footer = lambda canvas, current_doc: _pdf_page_footer(canvas, current_doc, font,title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path

