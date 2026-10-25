"""Deterministic report figures from computed dates and recorded observations."""
from datetime import date
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,features
from arabic_reshaper import reshape
from bidi.algorithm import get_display
from core.reports.exporters import report_date,_percentage_display


def canvas(title,height):
    candidates=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/tahoma.ttf')]
    font=next((p for p in candidates if p.exists()),None)
    if font is None:raise RuntimeError('فونت فارسی دارای دسترسی برای نمودار موجود نیست')
    image=Image.new('RGB',(1300,height),'white');draw=ImageDraw.Draw(image);native=features.check_feature('raqm')
    f=ImageFont.truetype(str(font),18,layout_engine=ImageFont.Layout.RAQM if native else ImageFont.Layout.BASIC)
    def label(pos,value,fill='#203044'):
        if native:draw.text(pos,str(value),font=f,fill=fill,direction='rtl')
        else:draw.text(pos,get_display(reshape(str(value))),font=f,fill=fill)
    label((700,18),title);return image,draw,label


def gantt_figures(project,result,path):
    outputs=[];tasks=result['order'];start=date.fromisoformat(result['start']);days=max(1,(date.fromisoformat(result['finish_boundary'])-start).days)
    sx=lambda value:340+int((date.fromisoformat(value)-start).days/days*890)
    by={a['id']:a for a in project['project_schedule_tasks']};base=(project.get('schedule_baselines') or [None])[-1]
    for page in range(0,len(tasks),24):
        ids=tasks[page:page+24];image,draw,label=canvas('گانت — قرمز بحرانی، خاکستری مبنا',130+len(ids)*42)
        coords={}
        for i,id in enumerate(ids):
            r=result['activities'][id];y=75+i*42;left,right=sx(r['start']),sx(r['finish_boundary']);coords[id]=(left,right,y)
            label((8,y),by[id].get('wbs_id','')+' / '+by[id]['title'])
            if base and id in base['result']['activities']:
                b=base['result']['activities'][id];draw.rectangle((sx(b['start']),y+22,max(sx(b['start'])+2,sx(b['finish_boundary'])),y+26),fill='#91a0b2')
            color='#c74459' if r['critical'] else '#347eaf'
            if r['milestone']:draw.polygon([(left,y),(left+8,y+9),(left,y+18),(left-8,y+9)],fill=color)
            else:draw.rectangle((left,y,max(left+3,right),y+18),fill=color)
        for rel in result['relationships']:
            if rel['pred'] in coords and rel['succ'] in coords:
                a,b=coords[rel['pred']],coords[rel['succ']];left=a[1] if rel['type'][0]=='F' else a[0];right=b[1] if rel['type'][1]=='F' else b[0]
                draw.line([(left,a[2]+9),(left+8,a[2]+9),(left+8,b[2]+9),(right,b[2]+9)],fill='#778798',width=1)
        label((340,48),report_date(start));label((1050,48),report_date(date.fromisoformat(result['finish_boundary'])))
        file=Path(str(path)+f'-gantt-{page//24+1}.png');file.parent.mkdir(parents=True,exist_ok=True);image.save(file);outputs.append({'path':str(file),'caption':'گانت و روابط — بخش '+str(page//24+1)})
    return outputs


def curve_figure(points,path):
    if not points:return []
    image,draw,label=canvas('منحنی S — آبی مبنا؛ نارنجی جاری؛ سبز واقعی؛ فقط نقاط ثبت‌شده',550)
    dates=[date.fromisoformat(p['date']) for p in points];span=max(1,(max(dates)-min(dates)).days)
    draw.line((80,70,80,450),fill='#37465a',width=2);draw.line((80,450,1230,450),fill='#37465a',width=2)
    for pct in [0,25,50,75,100]:
        y=450-pct*3.6;draw.line((80,y,1230,y),fill='#e0e6ed');label((15,y-10),str(pct)+'٪')
    for p,day in zip(points,dates):
        x=100+int((day-min(dates)).days/span*1080)
        label((x-40,470),report_date(day))
        for key,color in [('planned','#347eaf'),('planned_current','#d18a26'),('actual','#26976b')]:
            if p.get(key) is not None:
                y=450-float(p[key])*3.6;draw.ellipse((x-5,y-5,x+5,y+5),fill=color);label((x+7,y-12),_percentage_display(p[key]),color)
    file=Path(str(path)+'-curve.png');file.parent.mkdir(parents=True,exist_ok=True);image.save(file)
    return [{'path':str(file),'caption':'نقاط واقعی گزارش‌های ثبت‌شده؛ بدون میان‌یابی دوره مفقود'}]
