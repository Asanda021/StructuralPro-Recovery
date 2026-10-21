"""Extend a COPY of the prior synthetic ARCH-5 SQLite scenario; never recreate it."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import argparse,json,shutil
from core.platform.application import StructuralProApp
from core.takeoff.reviewed_aec import empty_system
from core.reports.architecture_detail_report import export,export_project

def run(reference_directory,output_directory):
 reference=Path(reference_directory).resolve();out=Path(output_directory).resolve()
 if out.exists():raise FileExistsError(out)
 if not (reference/'previous/package2/package1/db').is_dir():raise ValueError('سناریوی ذخیره‌شده قبلی لازم است؛ ایجاد مجدد مجاز نیست')
 out.mkdir(parents=True);shutil.copytree(reference,out/'previous');docs=out/'documents';docs.mkdir()
 a=StructuralProApp(out/'previous/previous/package2/package1/db');before=deepcopy(a.open_project('ARCH-5'));old_boq=deepcopy(before['boq']);inputs=[];documents={}
 for i in range(1,6):
  fl='L'+str(i);old=a.get_aec_system('ARCH-5','floor_finish',fl,'F-'+fl)['data'];g=deepcopy(old['architecture_detail']['geometry'])
  if (g['length_m'],g['width_m'],g['count'])!=('5','4','1'):raise ValueError('این سناریوی مصنوعی فقط مرجع صریح ۵×۴ و یک تکرار را می‌پذیرد')
  source=docs/('slope-'+fl+'.txt');source.write_text('EXPLICIT SYNTHETIC SOFTWARE TEST ONLY. '+fl+'; same documented 5x4 host and datum; slope base offset .4 m, corners .2/.3/.4 m; full depth opening (1,1) 1x1 m. No prices, density, recipe or waste.')
  documents[str(source)]=sha256(source.read_bytes()).hexdigest();base=Decimal(g['base_level_m'])+Decimal('.4')
  g.update(bottom_m='.4',layer_key='SLOPE-'+fl,coordinate_frame_ref='Same synthetic host local origin and axes',material_ref='مصالح مصنوعی شیب‌بندی؛ بدون مصرف فرضی',source_path=str(source),source_sha256=documents[str(source)],source_ref='SLOPE-ROOT-'+fl,approved_by='نویسنده مصنوعی شیب‌بندی',payment_ref='فقط حجم خالص اجرا',interface_ref='دیتایل مصنوعی تطبیق مختصات میزبان و آغاز لایه در فاصله صریح ۰٫۴ متر از تراز مبنا')
  z=dict(id='Z-'+fl,physical_key='SLOPE-PART-'+fl,source_ref='SLOPE-ZONE-'+fl,approved_by='نویسنده مصنوعی شیب‌بندی',datum_ref='تراز صریح مصنوعی',x_m='0',y_m='0',length_m='5',width_m='4',base_elevation_m=str(base),thickness_00_m='.2',thickness_10_m='.3',thickness_01_m='.4')
  h=dict(id='H-'+fl,physical_key='SLOPE-HOLE-'+fl,source_ref='SLOPE-OPENING-'+fl,approved_by='نویسنده مصنوعی شیب‌بندی',zone_id=z['id'],x_m='1',y_m='1',length_m='1',width_m='1',penetration='full_depth')
  d=empty_system('floor_finish',fl,'S-'+fl);d.update(measurement_policy='architecture_specialist_v1',building_id=old['building_id'],axis=old['axis'],source=dict(mode='manual',source_id='SYNTHETIC-SLOPE-'+fl,plan_ref='پلان مصنوعی محفوظ طبقه '+fl,detail_ref='دیتایل شیب‌بندی مصنوعی '+fl),architecture_detail=dict(contract='planar_slope_aec_v1',geometry=g,zones=[z],openings=[h]))
  inputs.append(deepcopy(d));a.save_aec_system_draft('ARCH-5',d,expected_revision=0);a.review_roof_system('ARCH-5','floor_finish',fl,'S-'+fl,expected_revision=1,reviewer='بازبین مستقل شیب‌بندی',note='مرجع مستقل: ناخالص ۷، کسر ۰٫۳۰۵ و خالص ۶٫۶۹۵ مترمکعب');a.commit_aec_system('ARCH-5','floor_finish',fl,'S-'+fl,expected_revision=2)
 initial=deepcopy(a.open_project('ARCH-5'));d=deepcopy(a.get_aec_system('ARCH-5','floor_finish','L3','S-L3')['data']);d.pop('roof_review')
 for k in ('thickness_00_m','thickness_10_m','thickness_01_m'):d['architecture_detail']['zones'][0][k]=str(Decimal(d['architecture_detail']['zones'][0][k])+Decimal('.1'))
 e=docs/'slope-L3-amendment.txt';e.write_text('EXPLICIT SYNTHETIC correction: add .1m to each corner; net area 19m2; delta volume 1.9m3. Other floors unchanged.');documents[str(e)]=sha256(e.read_bytes()).hexdigest()
 am=a.create_roof_amendment('ARCH-5','floor_finish','L3','S-L3',d,expected_revision=2,created_by='درخواست‌کننده مصنوعی',reason='اصلاح مستند مصنوعی طبقه سوم',evidence=dict(evidence_path=str(e),evidence_sha256=documents[str(e)],evidence_reference='مدرک مصنوعی افزایش ضخامت ۰٫۱ متر'))
 assert [Decimal(str(v)) for v in am['delta'].values()]==[Decimal('1.9')]
 a.review_beam_amendment('ARCH-5',am['id'],expected_revision=1,reviewer='بازبین مستقل اصلاحیه',note='کنترل اختلاف ۱٫۹ مترمکعب');a.apply_beam_amendment('ARCH-5',am['id'],expected_revision=1)
 # Acceptance must use a new SQLite connection, not just the service cache.
 a.store.close();a=StructuralProApp(out/'previous/previous/package2/package1/db')
 assert a.get_aec_system('ARCH-5','floor_finish','L3','S-L3')['revision']==3
 assert len(a.open_project('ARCH-5')['beam_amendments'])==len(before['beam_amendments'])+1
 p=a.open_project('ARCH-5');assert p['takeoffs']==initial['takeoffs']
 for k,v in before['reviewed_aec_systems'].items():assert p['reviewed_aec_systems'][k]==v
 for k,v in before['beam_amendments'].items():assert p['beam_amendments'][k]==v
 for row in old_boq:assert row in p['boq']
 quantities={}
 for i in range(1,6):
  floor='L'+str(i);key='aec:floor_finish:'+floor+':S-'+floor+':Z-'+floor;rows=[r for r in p['boq'] if r['source_id']==key];assert len(rows)==1;quantities[floor]=str(rows[0]['quantity']);assert Decimal(quantities[floor])==Decimal('8.595' if i==3 else '6.695')
  if i!=3:
   key=next(k for k,v in initial['reviewed_aec_systems'].items() if v['data']['system_id']=='S-'+floor);assert p['reviewed_aec_systems'][key]==initial['reviewed_aec_systems'][key]
  export_project(a,'ARCH-5',out/('floor-'+floor+'.csv'),format='csv',floor=floor)
 assert sum(Decimal(q) for q in quantities.values())==Decimal('35.375')
 for fmt in ('pdf','xlsx','docx','csv'):export(a,'ARCH-5','floor_finish','L3','S-L3',out/('slope.'+fmt),format=fmt)
 export_project(a,'ARCH-5',out/'all-architecture.csv',format='csv')
 assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';a.store.close()
 receipt=dict(synthetic_only=True,reference_directory=str(reference),documents=documents,boq_rows=len(p['boq']),prior_boq_rows=len(old_boq),old_records_and_amendments_preserved=True,four_other_floors_unchanged=True,per_floor_m3=quantities,slope_total_m3='35.375',amendment_delta_m3='1.9',amendment_id=am['id'],sqlite_integrity='ok',not_windows_acceptance=True)
 (out/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2));(out/'scenario.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));return receipt

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--reference-directory',required=True);parser.add_argument('--output-directory',required=True);args=parser.parse_args();print(json.dumps(run(args.reference_directory,args.output_directory),ensure_ascii=False))
