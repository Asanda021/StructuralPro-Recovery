"""Real vector PDF bytes for persistence/approval tests, not a symbolic URI."""
def vector_pdf(tmp_path):
    import pymupdf
    path=tmp_path/'source-evidence.pdf'
    if not path.exists():
        doc=pymupdf.open()
        for _ in range(5):
            page=doc.new_page(width=1000,height=1000)
            page.draw_line((0,0),(100,0))
            page.draw_rect((0,0,200,100))
        doc.save(path);doc.close()
    return str(path)
