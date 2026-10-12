"""Graphical PDF extraction for production drawing takeoff.

Uses PyMuPDF when available. Coordinates are preserved in PDF points and each
primitive keeps page/source identity. No engineering dimensions are inferred.
"""
from __future__ import annotations
from pathlib import Path
from .models import DrawingPrimitive
from .adapters import AdapterResult, DrawingSource, _path

class GraphicalPDFAdapter:
    extensions=(".pdf",)
    def read(self,path):
        p=_path(path)
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Install PyMuPDF to read graphical PDF drawings") from exc
        doc=fitz.open(str(p)); page_count=len(doc); out=[]
        for page_no,page in enumerate(doc,1):
            for idx,d in enumerate(page.get_drawings(),1):
                rect=d.get("rect")
                if rect is None: continue
                items=d.get("items") or ()
                for seg_no,item in enumerate(items,1):
                    op=item[0]
                    if op=="l":
                        a,b=item[1],item[2]
                        out.append(DrawingPrimitive("line",x=float(a.x),y=float(a.y),
                            x2=float(b.x),y2=float(b.y),layer=f"PDF_PAGE_{page_no}",
                            source_id=f"pdf:{p.name}:p{page_no}:d{idx}:s{seg_no}",
                            properties={"page":page_no,"pdf_operator":op}))
                    elif op=="re":
                        r=item[1]
                        out.append(DrawingPrimitive("rectangle",x=float(r.x0),y=float(r.y0),
                            width=float(r.width),height=float(r.height),
                            layer=f"PDF_PAGE_{page_no}",
                            source_id=f"pdf:{p.name}:p{page_no}:d{idx}:s{seg_no}",
                            properties={"page":page_no,"pdf_operator":op}))
                if not items:
                    out.append(DrawingPrimitive("rectangle",x=float(rect.x0),y=float(rect.y0),
                        width=float(rect.width),height=float(rect.height),
                        layer=f"PDF_PAGE_{page_no}",source_id=f"pdf:{p.name}:p{page_no}:d{idx}",
                        properties={"page":page_no}))
            for idx,word in enumerate(page.get_text("words") or (),1):
                x0,y0,x1,y1,text=word[:5]
                out.append(DrawingPrimitive("text",x=float(x0),y=float(y0),
                    width=float(x1-x0),height=float(y1-y0),text=str(text),
                    layer=f"PDF_TEXT_PAGE_{page_no}",
                    source_id=f"pdf:{p.name}:p{page_no}:w{idx}",
                    properties={"page":page_no}))
        doc.close()
        return AdapterResult(DrawingSource(p,"pdf",{"page_count":page_count}),
                             tuple(out),())
