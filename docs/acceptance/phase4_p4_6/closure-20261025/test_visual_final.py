from pathlib import Path
import json

def test_render_contacts():
 import fitz
 from PIL import Image,ImageDraw
 qa=Path('docs/acceptance/phase4_p4_6/closure-20261025');out=qa/'visual-final';out.mkdir(exist_ok=True)
 root=Path('/tmp/sp-closure-scenario-final');render=Path('/tmp/sp-closure-render-final-20261025')
 paths=[root/(x+'.pdf') for x in ('dashboard','package','materials')]+[root/'prior/progress.pdf',root/'prior/curve.pdf']
 paths += [render/'docx'/f'{x}.pdf' for x in ('dashboard','package')]+[render/'xlsx'/f'{x}.pdf' for x in ('dashboard','package','curve')]
 records=[]
 for p in paths:
  if not p.exists():continue
  with fitz.open(p) as d:
   tiles=[]
   for i,page in enumerate(d):
    pix=page.get_pixmap(matrix=fitz.Matrix(1,1));im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((480,650));tile=Image.new('RGB',(500,690),'#ddd');tile.paste(im,((500-im.width)//2,20));ImageDraw.Draw(tile).text((10,670),f'{p.parent.name}/{p.stem} page{i+1}',fill='black');tiles.append(tile)
   sheet=Image.new('RGB',(500*min(3,len(tiles)),690*((len(tiles)+2)//3)),'white')
   for i,im in enumerate(tiles):sheet.paste(im,((i%3)*500,(i//3)*690))
   name=p.parent.name+'-'+p.stem+'.png';sheet.save(out/name);records.append({'source':str(p),'pages':len(d),'contact':name})
 (qa/'visual-pages-final.json').write_text(json.dumps(records,indent=2))
