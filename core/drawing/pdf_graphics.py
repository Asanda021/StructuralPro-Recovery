"""Inventory PDF primitives in page points without inferring engineering dimensions."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256

from core.drawings.pdf_engine import require_current_pdf
from .adapters import AdapterResult, DrawingSource, _path
from .models import DrawingPrimitive


class GraphicalPDFAdapter:
    extensions = (".pdf",)

    def read(self, path):
        p = _path(path)
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("Install PyMuPDF to read graphical PDF drawings") from exc
        data = p.read_bytes()
        digest = sha256(data).hexdigest()
        primitives, pages, warnings = [], [], []
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass or document.is_repaired or not len(document):
                raise ValueError("PDF requires an intact, readable source")
            for page_no, page in enumerate(document, 1):
                operators = Counter()
                images = len(page.get_image_info())
                for path_no, drawing in enumerate(page.get_drawings(), 1):
                    for segment_no, item in enumerate(drawing.get("items") or (), 1):
                        op = item[0]
                        operators[op] += 1
                        anchor = f"pdf:{p.name}:p{page_no}:d{path_no}:s{segment_no}"
                        properties = {"page": page_no, "pdf_operator": op}
                        common = {"layer": f"PDF_PAGE_{page_no}", "source_id": anchor}
                        if op == "l":
                            a, b = item[1:3]
                            primitive = DrawingPrimitive("line", x=a.x, y=a.y, x2=b.x, y2=b.y,
                                                         properties=properties, **common)
                        elif op == "re":
                            rect = item[1]
                            primitive = DrawingPrimitive("rectangle", x=rect.x0, y=rect.y0,
                                                         width=rect.width, height=rect.height,
                                                         properties=properties, **common)
                        elif op in {"qu", "c"}:
                            kind = "quadrilateral" if op == "qu" else "bezier"
                            positions = tuple(item[1]) if op == "qu" else item[1:]
                            points = tuple((point.x, point.y) for point in positions)
                            properties.update(points=points, needs_confirmation=True)
                            # These types keep the real vertices and controls. The
                            # legacy primitive estimator must not meter a bounds box.
                            primitive = DrawingPrimitive(kind, properties=properties, **common)
                        else:
                            warnings.append(f"Page {page_no}: unsupported PDF path operator {op!r}")
                            continue
                        primitives.append(primitive)
                words = page.get_text("words")
                for word_no, (x0, y0, x1, y1, word, *_) in enumerate(words, 1):
                    primitives.append(DrawingPrimitive(
                        "text", x=x0, y=y0, width=x1-x0, height=y1-y0, text=word,
                        layer=f"PDF_TEXT_PAGE_{page_no}", source_id=f"pdf:{p.name}:p{page_no}:w{word_no}",
                        properties={"page": page_no},
                    ))
                if images:
                    kind = "hybrid" if operators or words else "raster"
                else:
                    kind = "vector" if operators else "text" if words else "blank"
                pages.append({
                    "page": page_no, "content_kind": kind, "rotation": page.rotation,
                    "width_pt": page.rect.width, "height_pt": page.rect.height,
                    "operators": dict(operators), "image_count": images, "word_count": len(words),
                })
        require_current_pdf(p, digest)
        source = DrawingSource(p, "pdf", {
            "page_count": len(pages), "pages": pages, "source_sha256": digest,
            "coordinate_space": "unrotated_pdf_points",
        })
        return AdapterResult(source, tuple(primitives), tuple(warnings))
