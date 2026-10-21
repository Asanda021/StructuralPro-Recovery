"""Reproducible synthetic PDF benchmark and three-roof report evidence.

Run with the project Python: python scripts/phase2_pdf_acceptance_probe.py OUT.
Not a real-plan approval, stress-capacity guarantee or Windows performance test.
"""
from pathlib import Path
from hashlib import sha256
from decimal import Decimal
import sys,json,time,resource,platform
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import fitz
from test_phase2_pdf_roof import bound
from core.drawings.pdf_engine import PDFDrawingEngine


def run(root):
    root.mkdir(parents=True,exist_ok=True);results={'fixture':'synthetic explicit phase-one rectangular roof schedules','platform':platform.platform(),'roofs':{}}
    for kind in ('solid_slab','joist_block','joist_foam'):
        out=root/kind;out.mkdir(exist_ok=True)
        app,session,item,rec,d=bound(out,kind)
        app.save_aec_system_draft('P',d,expected_revision=0)
        app.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='independent synthetic test reviewer',note='exact test oracle comparison')
        app.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
        project=app.open_project('P');totals={}
        for row in project['takeoffs']:
            for q in row['quantities']:totals[q['code']]=totals.get(q['code'],Decimal(0))+Decimal(str(q['amount']))
        outputs={}
        for ext in ('pdf','xlsx','docx','csv'):
            path=out/('roof.'+ext);app.export_roof_detail_report('P',kind,'L1','S1',str(path),format=ext)
            outputs[ext]={'bytes':path.stat().st_size,'sha256':sha256(path.read_bytes()).hexdigest()}
        results['roofs'][kind]={'session_id':rec['session_id'],'measurement_id':item.id,'boq_count':len(project['boq']),'source':d['source'],'totals':{k:str(v) for k,v in totals.items()},'outputs':outputs,'sqlite_integrity':app.store.db.execute('pragma integrity_check').fetchone()[0]}
        app.store.close()
    path=root/'large-synthetic.pdf'
    with fitz.open() as pdf:
        for number in range(24):
            page=pdf.new_page(width=1200,height=900);shape=page.new_shape()
            for i in range(12000):
                x=10+(i%1000)*1.17;y=10+(i//1000)*67
                shape.draw_line((x,y),(x+.5,y+40))
            shape.finish(color=(0,0,0),width=.1);shape.commit()
            page.insert_text((20,30),'SYNTHETIC BENCHMARK '+str(number+1))
        pdf.save(path,deflate=False)
    peak_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;t=time.perf_counter()
    engine=PDFDrawingEngine(path);count=engine.page_count;opened=time.perf_counter()-t;times=[]
    for page in (1,12,24):
        t=time.perf_counter();image=engine.render(page,150);times.append({'page':page,'seconds':time.perf_counter()-t,'png_bytes':len(image)})
    engine.close()
    results['benchmark']={'source_bytes':path.stat().st_size,'pages':count,'vector_segments_per_page':12000,'open_seconds':opened,'render_dpi':150,'renders':times,'process_peak_rss_before_kib':peak_before,'process_peak_rss_after_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'note':'high-water process RSS; not a claim of maximum supported PDF size'}
    (root/'receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'roofs':{k:{a:v[a] for a in ('totals','boq_count','sqlite_integrity')} for k,v in results['roofs'].items()},'benchmark':results['benchmark']},ensure_ascii=False))

if __name__=='__main__':run(Path(sys.argv[1]).resolve())
