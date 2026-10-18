"""P1 #3: optional source-bound XY-centre comparison for existing pile spatial audit.

No automatic coordinate binding/migration of legacy pile records is implied.
Even an identical SHA-pinned file does not prove drawing authenticity.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from core.takeoff.bored_pile_ownership_preflight import OwnershipError, _object, _id, _hash, read_evidence
from core.takeoff.bored_pile_joint_crosswalk import _num

POLICY='bored_pile_center_source_crosswalk_v1'
_KEYS=('policy','project_id','floor_id','group_id','input_sha256',
       'coordinate_ref','vertical_datum_ref','source_reference','prepared_by','reviewer','centers')
_CENTER=('pile_id','pile_physical_id','x_m','y_m','source_ref')

def audit(data, compiled, spatial, *, center_path, center_sha256):
    """Exact center coordinates required for every spatial link; never returns BOQ rows.

    The complete input SHA is compared, but it is NOT a drawing signature.
    Run the existing full spatial/ownership crosswalk separately.
    """
    center=read_evidence(str(center_path),_hash(center_sha256,'هش مرکز شمع'))
    _object(center,_KEYS,'سند مستقل مختصات افقی شمع')
    if center['policy']!=POLICY:
        raise OwnershipError('قرارداد مختصات شمع ناشناخته است')
    for field in ('project_id','floor_id','group_id','coordinate_ref','vertical_datum_ref'):
        expected=(data['datum'][field] if field in ('coordinate_ref','vertical_datum_ref') else data[field])
        if _id(center[field],field)!=_id(expected,field):
            raise OwnershipError('سند مرکز شمع با هویت یا مبنای مدل برابر نیست')
    if _hash(center['input_sha256'],'هش ورودی')!=_hash(compiled['source_sha256'],'هش موتور'):
        raise OwnershipError('نسخه ورودی شمع با سند مستقل مختصات متفاوت است')
    for field in ('source_reference','prepared_by','reviewer'):_id(center[field],field)
    if center['prepared_by'].casefold()==center['reviewer'].casefold():
        raise OwnershipError('بازبین مستقل مختصات شمع وجود ندارد')
    piles={p['id']:p for p in data['piles']}
    if len(piles)!=len(data['piles']):raise OwnershipError('شناسه شمع تکراری است')
    centers=center['centers']
    if not isinstance(centers,list) or len(centers)!=len(piles):
        raise OwnershipError('تمام شمع‌ها باید سند مختصات مستقل داشته باشند')
    mapping={}
    for item in centers:
        _object(item,_CENTER,'مرکز مستقل شمع')
        key=_id(item['pile_id'],'هویت شمع')
        if key in mapping or key not in piles or item['pile_physical_id']!=piles[key]['physical_id']:
            raise OwnershipError('شناسه مرکز شمع مفقود، تکراری یا ناهماهنگ است')
        _id(item['source_ref'],'مرجع جانمایی')
        mapping[key]=(_num(item['x_m'],'مرکز X'),_num(item['y_m'],'مرکز Y'))
    if set(mapping)!=set(piles):raise OwnershipError('مرکز همه شمع‌ها شناسایی نشده است')
    links=spatial.get('links')
    if not isinstance(links,list) or not links:raise OwnershipError('مدرک سه‌بعدی شمع فاقد رابط است')
    for link in links:
        pid=link.get('pile_id')
        if pid not in mapping or (_num(link.get('pile_center_x_m'),'X سند سه‌بعدی'),
                                   _num(link.get('pile_center_y_m'),'Y سند سه‌بعدی'))!=mapping[pid]:
            raise OwnershipError('مرکز سه‌بعدی با سند مستقل شمع یکسان نیست')
    return {'policy':POLICY,'status':'PILE_CENTER_SOURCE_PREVIEW_ONLY',
            'checked_pile_count':len(piles),'checked_link_count':len(links),
            'ready_for_boq':False,'commit_allowed':False,'rows':[],
            'blockers':['سند مختصات با ورودی و مدل برابر است، ولی اصالت نقشه و مهر مهندس مستقل تأیید نشده است',
                        'ممیزی کامل موتور هندسه شمع/کلاهک، مالکیت مشترک و داده تاریخی همچنان لازم است']}
