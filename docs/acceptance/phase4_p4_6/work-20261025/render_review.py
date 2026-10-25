from pathlib import Path
import fitz,json
from PIL import Image,ImageOps,ImageDraw
out=Path('docs/acceptance/phase4_p4_6/work-20261025/visual');out.mkdir(exist_ok=True)
roots=[Path('/tmp/structuralpro-final-20261025'),Path('/tmp/sp-docx-dashboard-20261025'),Path('/tmp/sp-docx-package-20261025'),Path('/tmp/sp-report-render-20261025')]
receipt=[]
for root in roots:
 for p in root.rglob('*.pdf'):
  if p.name=='plan.pdf':continue
  d=fitz.open(p);thumbs=[]
  for i,page in enumerate(d):
   pix=page.get_pixmap(matrix=fitz.Matrix(1,1));im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((380,540));tile=Image.new('RGB',(400,570),'#dddddd');tile.paste(im,((400-im.width)//2,20));ImageDraw.Draw(tile).text((10,550),f'{p.stem} {i+1}',fill='black');thumbs.append(tile)
  label=(p.parent.name+'-'+p.stem);sheet=Image.new('RGB',(400*min(4,len(thumbs)),570*((len(thumbs)+3)//4)),'white')
  for i,im in enumerate(thumbs):sheet.paste(im,((i%4)*400,(i//4)*570))
  sheet.save(out/(label+'.png'));receipt.append({'source':str(p),'pages':len(d),'contact':label+'.png'})
(out.parent/'render-review.json').write_text(json.dumps(receipt,indent=2))
