"""The real progress chart must fit one printed spreadsheet page."""
from PIL import Image
from openpyxl import load_workbook
from core.reports.exporters import export_xlsx

def test_report_figure_sheet_has_complete_single_page_print_area(tmp_path):
    image=tmp_path/'curve.png';Image.new('RGB',(1200,400),'white').save(image)
    output=tmp_path/'curve.xlsx'
    export_xlsx([{'عنوان':'پیشرفت','مقدار':'75'}],output,metadata={'_figures':[{'caption':'نمودار پیشرفت','path':str(image)}]})
    book=load_workbook(output);sheet=book.worksheets[-1]
    assert len(sheet._images)==1
    assert sheet.sheet_view.rightToLeft
    assert sheet.sheet_properties.pageSetUpPr.fitToPage
    assert sheet.page_setup.orientation=='landscape'
    assert sheet.page_setup.fitToWidth==1 and sheet.page_setup.fitToHeight==1
    assert sheet.print_area and 'P' in str(sheet.print_area)
    assert 'A1:P1' in {str(r) for r in sheet.merged_cells.ranges}
    assert sheet.oddFooter.center.text=='صفحه &P از &N'
