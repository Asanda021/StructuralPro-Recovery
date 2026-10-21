"""Independent, fail-closed, Decimal stair takeoff preview.

DOES NOT create/commit BOQ, reviews, or SQLite. Every input is explicitly
sourced; physical ids prevent duplicate *declared* objects, not fraudulently
renamed shapes or full 3-D structural intersection analysis.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from typing import Any

SCHEMA = 'stair_specialist_v1'
BAR_GROUPS = frozenset({'flight_main', 'flight_distribution', 'flight_top_extra',
                       'flight_bottom_extra', 'landing', 'starter', 'connection',
                       'special'})
REBAR_LENGTH_PARTS = ('straight_m', 'bend_m', 'hook_m', 'anchorage_m', 'lap_m')
UNITS = {'length': 'm', 'area': 'm2', 'volume': 'm3', 'mass': 'kg', 'diameter': 'mm'}

class StairValidationError(ValueError):
    """Rejected geometry or missing independent source (fail closed)."""


def require_dict(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise StairValidationError(f'{label}: object required')
    return value


def keys(obj: dict, fields: set, label: str) -> None:
    absent = fields - obj.keys()
    extra = obj.keys() - fields
    if absent or extra:
        raise StairValidationError(f'{label}: missing={sorted(absent)} unexpected={sorted(extra)}')


def text(obj: dict, key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StairValidationError(f'{key}: documented nonempty text required')
    return value.strip()


def d(obj: dict, key: str, *, nonnegative: bool = False) -> Decimal:
    value = obj.get(key)
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (str, int, Decimal)):
        raise StairValidationError(f'{key}: exact Decimal input required, float/unknown forbidden')
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise StairValidationError(f'{key}: invalid exact decimal') from None
    if not number.is_finite() or (number < 0 if nonnegative else number <= 0):
        raise StairValidationError(f'{key}: invalid sign or non-finite')
    return number


def integer(obj: dict, key: str, *, min_value: int = 1) -> int:
    n = d(obj, key, nonnegative=True)
    if n != n.to_integral_value() or n < min_value:
        raise StairValidationError(f'{key}: documented integer >= {min_value} required')
    return int(n)


def equal(a: Decimal, b: Decimal, why: str) -> None:
    if a != b:
        raise StairValidationError(f'{why}: inconsistent documented values {a} and {b}')


def overlapping(a: tuple, b: tuple) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def inside(outer: tuple, inner: tuple, *, strictly: bool = False) -> bool:
    if strictly:
        return outer[0] < inner[0] < inner[2] < outer[2] and outer[1] < inner[1] < inner[3] < outer[3]
    return outer[0] <= inner[0] < inner[2] <= outer[2] and outer[1] <= inner[1] < inner[3] <= outer[3]


def canonical_json(obj: Any) -> str:
    def no_float(v: Any) -> Any:
        if isinstance(v, float):
            raise StairValidationError('float input forbidden everywhere')
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, dict):
            return {k: no_float(val) for k, val in v.items()}
        if isinstance(v, list):
            return [no_float(val) for val in v]
        if isinstance(v, (str, int, bool)) or v is None:
            return v
        raise StairValidationError('unsupported input type')
    return json.dumps(no_float(obj), sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _atan_series(x: Decimal) -> Decimal:
    """Arctan Taylor series on a reduced argument; Decimal only."""
    if not 0 <= x <= Decimal('0.5'):
        raise StairValidationError('atan argument not reduced')
    total = Decimal(0)
    power = x
    sign = 1
    for n in range(2000):
        term = power / Decimal(2*n+1)
        total += term if sign > 0 else -term
        if abs(term) < Decimal('1e-69'):
            return total
        power *= x*x
        sign *= -1
    raise StairValidationError('atan series did not converge')


def _slope_angle_degrees(rise: Decimal, run: Decimal) -> Decimal:
    # Machin's identity; argument reduction prevents slow near-1 series.
    pi = Decimal(16)*_atan_series(Decimal(1)/5)-Decimal(4)*_atan_series(Decimal(1)/239)
    ratio = rise/run
    if ratio > 1:
        small = run/rise
        angle = pi/2 - 2*_atan_series(small/(1+(1+small*small).sqrt()))
    else:
        angle = 2*_atan_series(ratio/(1+(1+ratio*ratio).sqrt()))
    return angle*Decimal(180)/pi


def preview(data: dict) -> dict:
    """Take off documented axis-aligned flights, landings, step wedges, form faces and bar schedules.

    Coordinates and elevation use metres; flight's start elevation is the
    TOP of waist at the low end. Thickness is measured NORMAL to inclined face.
    Flight plan rectangle is defined by horizontal run; its gross volume uses
    the longitudinal sloping length. Full-depth *interior* plan voids remove
    projected area × thickness / cos(theta). More complex cutouts are blocked.
    """
    with localcontext() as ctx:
        ctx.prec = 65
        return _preview(data)


def _preview(data: dict) -> dict:
    require_dict(data, 'input')
    keys(data, {'schema', 'metadata', 'units', 'flights', 'landings', 'steps',
                'voids', 'connections', 'form_faces', 'rebars', 'scope'}, 'root')
    if data['schema'] != SCHEMA or data['units'] != UNITS:
        raise StairValidationError('schema or dimensional units mismatch')
    m = require_dict(data['metadata'], 'metadata')
    keys(m, {'project_id', 'floor_id', 'stair_id', 'source_ref', 'approved_by',
             'story_start_z_m','story_end_z_m','story_height_m','story_ref'}, 'metadata')
    for k in ('project_id','floor_id','stair_id','source_ref','approved_by','story_ref'):
        text(m, k)
    story_start=d(m,'story_start_z_m',nonnegative=True)
    story_end=d(m,'story_end_z_m',nonnegative=True)
    story_height=d(m,'story_height_m')
    equal(story_end-story_start,story_height,'story height vs elevations')
    scope = require_dict(data['scope'], 'scope')
    keys(scope, {'steps', 'landings', 'connections', 'reinforcement', 'formwork', 'scope_ref'}, 'scope')
    for name in ('steps', 'landings', 'connections', 'reinforcement', 'formwork'):
        if scope[name] != 'fully_documented':
            raise StairValidationError(f'{name}: documented complete scope required; unknown is not zero')
    text(scope, 'scope_ref')
    for k in ('flights', 'landings', 'steps', 'voids', 'connections', 'form_faces', 'rebars'):
        if not isinstance(data[k], list):
            raise StairValidationError(f'{k}: explicit array required')
    if not data['flights']:
        raise StairValidationError('at least one flight required')
    if not data['rebars']:
        raise StairValidationError('reinforcement detail required for RC stair')
    seen: set[str] = set()
    objects: dict[str, dict] = {}
    rows: list[dict] = []
    faces: dict[str, Decimal] = {}
    surfaces: dict[str, dict] = {}
    voids_by: dict[str, list] = {}
    formulas: list[dict] = []

    def unique_id(id_: str, label: str) -> None:
        if id_ in seen:
            raise StairValidationError(f'{label}: repeated physical id {id_}')
        seen.add(id_)

    def emit(group: str, unit: str, value: Decimal, phys: str, ref: str, formula: str) -> None:
        if not value.is_finite() or value <= 0:
            raise StairValidationError(f'{group}: nonpositive measured quantity')
        if unit not in {'m3', 'm2', 'kg'}:
            raise StairValidationError('unsupported output unit')
        rows.append({'operation': group, 'unit': unit, 'quantity_exact': str(value),
                     'physical_id': phys, 'source_ref': ref, 'formula': formula,
                     'source_id': f"{m['stair_id']}:{phys}:{group}"})

    for p in data['flights']:
        require_dict(p, 'flight')
        keys(p, {'id', 'source_ref', 'direction', 'start_x_m', 'start_y_m',
                 'start_top_z_m', 'end_top_z_m', 'horizontal_run_m', 'width_m',
                 'tread_count', 'riser_count', 'tread_m', 'riser_m',
                 'normal_waist_thickness_m', 'exclusion_ref'}, 'flight')
        id_, ref = text(p, 'id'), text(p, 'source_ref')
        unique_id(id_, 'flight')
        if p['direction'] not in ('x_positive', 'x_negative'):
            raise StairValidationError('only x-positive/negative documented straight flights supported')
        x = d(p, 'start_x_m', nonnegative=True)
        y = d(p, 'start_y_m', nonnegative=True)
        z0 = d(p, 'start_top_z_m', nonnegative=True)
        z1 = d(p, 'end_top_z_m', nonnegative=True)
        run, width = d(p, 'horizontal_run_m'), d(p, 'width_m')
        rise = z1-z0
        if rise <= 0:
            raise StairValidationError('end-top elevation must exceed start-top elevation')
        nr, nt = integer(p, 'riser_count'), integer(p, 'tread_count')
        equal(d(p, 'riser_m')*nr, rise, 'flight riser schedule')
        equal(d(p, 'tread_m')*nt, run, 'flight tread schedule')
        thick = d(p, 'normal_waist_thickness_m')
        text(p, 'exclusion_ref')
        sloped = (run*run+rise*rise).sqrt()
        factor = sloped/run
        footprint = (x, y, x+run, y+width) if p['direction']=='x_positive' else (x-run, y, x, y+width)
        if footprint[0] < 0:
            raise StairValidationError('negative footprint coordinates out of scope')
        objects[id_] = {'kind':'flight', 'rect':footprint, 'z_low':z0, 'z_high':z1,
                        'run':run, 'rise':rise, 'width':width, 'thick':thick,
                        'sloped':sloped, 'factor':factor, 'slope_angle_deg':_slope_angle_degrees(rise,run),
                        'direction':p['direction'],
                        'tread':d(p, 'tread_m'), 'riser':d(p, 'riser_m'),
                        'tread_count':nt, 'source_ref':ref}
    for p in data['landings']:
        require_dict(p, 'landing')
        keys(p, {'id', 'source_ref', 'x_m', 'y_m', 'length_m', 'width_m',
                 'top_z_m', 'thickness_m', 'exclusion_ref'}, 'landing')
        id_, ref = text(p, 'id'), text(p, 'source_ref')
        unique_id(id_, 'landing')
        x,y = d(p,'x_m',nonnegative=True),d(p,'y_m',nonnegative=True)
        length,width = d(p,'length_m'),d(p,'width_m')
        top, thick = d(p,'top_z_m',nonnegative=True),d(p,'thickness_m')
        if top < thick:
            raise StairValidationError('landing bottom below local datum is outside contract')
        text(p,'exclusion_ref')
        objects[id_] = {'kind':'landing','rect':(x,y,x+length,y+width),
                        'z_low':top,'z_high':top,'thick':thick,'source_ref':ref}
    flight_objects=[o for o in objects.values() if o['kind']=='flight']
    equal(min(o['z_low'] for o in flight_objects),story_start,'stair low end vs documented story')
    equal(max(o['z_high'] for o in flight_objects),story_end,'stair high end vs documented story')
    ids=list(objects)
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            if overlapping(objects[a]['rect'],objects[b]['rect']):
                raise StairValidationError(f'overlapping concrete footprints {a}, {b}; 3-D complex joining not supported')

    # A connection asserts a geometrically matching interface, not another payable solid.
    connections=set()
    for c in data['connections']:
        require_dict(c,'connection')
        keys(c, {'id','flight_id','landing_id','flight_end','landing_edge',
                 'source_ref','interface_kind'},'connection')
        id_=text(c,'id');unique_id(id_,'connection')
        f,l=objects.get(text(c,'flight_id')),objects.get(text(c,'landing_id'))
        if f is None or l is None or f['kind']!='flight' or l['kind']!='landing':
            raise StairValidationError('connection references unknown flight/landing')
        if c['flight_end'] not in ('low','high') or c['landing_edge'] not in ('left','right'):
            raise StairValidationError('unsupported flight/landing interface direction')
        if c['interface_kind']!='shared_boundary_no_extra_volume':
            raise StairValidationError('additional joint concrete needs a separate reviewed 3-D contract')
        fr, lr=f['rect'],l['rect']
        xboundary = fr[2] if (f['direction']=='x_positive')==(c['flight_end']=='high') else fr[0]
        ledge = lr[0] if c['landing_edge']=='left' else lr[2]
        equal(xboundary, ledge, 'connection boundary')
        if max(fr[1],lr[1])>=min(fr[3],lr[3]):
            raise StairValidationError('connection missing full-length common interface')
        equal(f['z_high'] if c['flight_end']=='high' else f['z_low'], l['z_low'], 'connection top elevation')
        pair=(c['flight_id'],c['landing_id'],c['flight_end'])
        if pair in connections: raise StairValidationError('duplicate connection interface')
        connections.add(pair)
        text(c,'source_ref')
    for fid, f in objects.items():
        if f['kind']!='flight':continue
        for lid,l in objects.items():
            if l['kind']!='landing':continue
            if (f['rect'][0] in (l['rect'][0],l['rect'][2]) or f['rect'][2] in (l['rect'][0],l['rect'][2])) and max(f['rect'][1],l['rect'][1])<min(f['rect'][3],l['rect'][3]):
                if not any(p[0]==fid and p[1]==lid for p in connections):
                    raise StairValidationError(f'undeclared flight-landing contact: {fid}/{lid}')

    # Void full-depth interior cutouts only; touching edges/rebates/partial-depth blocked.
    for v in data['voids']:
        require_dict(v, 'void')
        keys(v, {'id', 'owner_id', 'source_ref', 'x_m','y_m','length_m','width_m',
                 'penetration','reveal_form_area_m2','reveal_ref'}, 'void')
        id_, owner=text(v,'id'),text(v,'owner_id')
        unique_id(id_,'void')
        if owner not in objects or v['penetration']!='full_waist_or_landing':
            raise StairValidationError('void unsupported owner/penetration')
        x,y=d(v,'x_m',nonnegative=True),d(v,'y_m',nonnegative=True)
        rect=(x,y,x+d(v,'length_m'),y+d(v,'width_m'))
        if not inside(objects[owner]['rect'],rect,strictly=True):
            raise StairValidationError('only strictly interior full-depth rectangular voids supported')
        for other in voids_by.get(owner,[]):
            if overlapping(other['rect'],rect):raise StairValidationError('overlapping voids')
        area=d(v,'length_m')*d(v,'width_m')
        reveal=d(v,'reveal_form_area_m2',nonnegative=True)
        text(v,'source_ref');text(v,'reveal_ref')
        voids_by.setdefault(owner,[]).append({'id':id_,'rect':rect,'area':area,'reveal':reveal,'ref':text(v,'source_ref')})

    for id_,o in objects.items():
        rect=o['rect']; area=(rect[2]-rect[0])*(rect[3]-rect[1]); cut=sum((v['area'] for v in voids_by.get(id_,[])),Decimal(0))
        if cut>=area:raise StairValidationError('voids consume entire component')
        factor=o['factor'] if o['kind']=='flight' else Decimal(1)
        gross=area*o['thick']*factor; deduct=cut*o['thick']*factor
        emit('waist_concrete' if o['kind']=='flight' else 'landing_concrete','m3',gross-deduct,id_,o['source_ref'],
             '((plan length×width−full-depth interior void plan area)×normal thickness×sloped length/run)' if o['kind']=='flight'
             else '(landing plan area−full-depth void plan area)×thickness')
        formulas.append({'component':id_,'plan_area_m2':str(area),'void_area_m2':str(cut),
                         'volume_gross_m3':str(gross),'volume_deduction_m3':str(deduct),
                         'volume_net_m3':str(gross-deduct),
                         'sloped_length_m':str(o['sloped']) if o['kind']=='flight' else None,
                         'slope_angle_deg':str(o['slope_angle_deg']) if o['kind']=='flight' else None,
                         'slope_direction':o['direction'] if o['kind']=='flight' else None})
        if o['kind']=='flight':
            L,t,w=o['sloped'],o['thick'],o['width']
            vals={'underside':(area-cut)*o['factor'], 'side_near':L*t,'side_far':L*t,
                  'end_low':w*t,'end_high':w*t}
        else:
            xlen,ylen=rect[2]-rect[0],rect[3]-rect[1]
            vals={'underside':area-cut,'side_left':ylen*o['thick'],'side_right':ylen*o['thick'],
                  'side_near':xlen*o['thick'],'side_far':xlen*o['thick']}
        for k,val in vals.items():faces[f'{id_}:{k}']=val
        for v in voids_by.get(id_,[]):
            faces[f"{id_}:reveal:{v['id']}"]=v['reveal']

    # Triangular wedges must be explicitly independent of the waist body.
    steps_by:dict[str,list[dict]]={}
    for s in data['steps']:
        require_dict(s,'step')
        keys(s,{'id','flight_id','source_ref','separation_detail_ref',
                'physical_scope','x_m','y_m','run_m','rise_m','width_m'},'step')
        id_,owner=text(s,'id'),text(s,'flight_id')
        unique_id(id_,'step')
        f=objects.get(owner)
        if f is None or f['kind']!='flight' or s['physical_scope']!='triangular_wedge_above_waist_exclusive':
            raise StairValidationError('independent wedge/flight separation contract required')
        text(s,'source_ref');text(s,'separation_detail_ref')
        x,y=d(s,'x_m',nonnegative=True),d(s,'y_m',nonnegative=True)
        run,rise,width=d(s,'run_m'),d(s,'rise_m'),d(s,'width_m')
        equal(run,f['tread'],'step width of horizontal tread vs documented schedule')
        equal(rise,f['riser'],'step riser vs documented schedule')
        equal(width,f['width'],'step across flight width')
        rect=(x,y,x+run,y+width)
        if not inside(f['rect'],rect):raise StairValidationError('step outside flight plan')
        for v in voids_by.get(owner,[]):
            if overlapping(v['rect'],rect):raise StairValidationError('step overlaps full-depth void')
        for prior in steps_by.get(owner,[]):
            if overlapping(prior['rect'],rect):raise StairValidationError('duplicate step wedge footprint')
        steps_by.setdefault(owner,[]).append({'id':id_,'rect':rect})
        emit('step_concrete','m3',run*rise*width/Decimal(2),id_,text(s,'source_ref'),
             '(tread run×riser height/2)×step width, independent wedge above waist')
        faces.update({f'{id_}:tread_top':run*width, f'{id_}:riser':rise*width,
                      f'{id_}:side_near':run*rise/Decimal(2),f'{id_}:side_far':run*rise/Decimal(2),
                      f'{id_}:waist_contact':(run*run+rise*rise).sqrt()*width})
    for fid,f in objects.items():
        if f['kind']!='flight':continue
        if len(steps_by.get(fid,[])) != f['tread_count']:
            raise StairValidationError('incomplete independent wedge schedule; zero not inferred')
        # Strict full tread lattice, not merely matching total count.
        expected=[]
        for i in range(f['tread_count']):
            r=f['rect']; x=r[0]+Decimal(i)*f['tread']
            expected.append((x,r[1],x+f['tread'],r[3]))
        if {s['rect'] for s in steps_by[fid]}!=set(expected):
            raise StairValidationError('wedge placement not aligned with documented full tread lattice')

    face_details=[]
    seen_face=set()
    for f in data['form_faces']:
        require_dict(f,'form face')
        keys(f,{'key','physical_id','source_ref','treatment','reviewed_by','reason'},'form face')
        key=text(f,'key');physical=text(f,'physical_id')
        unique_id(physical,'physical form face')
        if key not in faces or key in seen_face:
            raise StairValidationError(f'unknown or duplicated form face {key}')
        seen_face.add(key)
        treatment=f['treatment']
        if treatment not in ('form','contact','no_form'):
            raise StairValidationError('formwork treatment must be explicitly reviewed')
        for k in ('source_ref','reviewed_by','reason'):text(f,k)
        area=faces[key]
        face_details.append({'key':key,'geometry_area_m2':str(area),
                             'payment_area_m2':str(area if treatment=='form' else Decimal(0)),
                             'treatment':treatment,'source_ref':text(f,'source_ref')})
        if treatment=='form' and area>0:
            emit('formwork','m2',area,physical,text(f,'source_ref'),f'explicit approved face {key}; geometric area')
    if seen_face!=faces.keys():
        raise StairValidationError(f'unscheduled form faces: {sorted(faces.keys()-seen_face)}')

    for r in data['rebars']:
        require_dict(r,'rebar')
        fields={'id','physical_id','owner_id','group','source_ref','detail_ref','shape_ref',
                'mass_ref','diameter_mm','count','unit_mass_kg_m',*REBAR_LENGTH_PARTS}
        keys(r,fields,'rebar')
        id_,phys=text(r,'id'),text(r,'physical_id')
        unique_id(phys,'rebar physical series')
        if text(r,'owner_id') not in objects:
            raise StairValidationError('unknown rebar owning member')
        if r['group'] not in BAR_GROUPS:
            raise StairValidationError('unsupported rebar group')
        for k in ('source_ref','detail_ref','shape_ref','mass_ref'):text(r,k)
        d(r,'diameter_mm');count=integer(r,'count');unit_mass=d(r,'unit_mass_kg_m')
        lengths=[d(r,k,nonnegative=True) for k in REBAR_LENGTH_PARTS]
        if lengths[0]<=0:raise StairValidationError('rebar straight/cut geometry missing')
        mass=sum(lengths,Decimal(0))*unit_mass*count
        emit('rebar_'+r['group'],'kg',mass,phys,text(r,'source_ref'),
             '(straight + bend + hook + anchorage + lap)×documented unit mass×explicit count')

    groups_by_owner={(r['owner_id'],r['group']) for r in data['rebars']}
    for id_,o in objects.items():
        required={'flight_main','flight_distribution'} if o['kind']=='flight' else {'landing'}
        if not all((id_,group) in groups_by_owner for group in required):
            raise StairValidationError(f'essential rebar detail missing for {id_}: {required}')

    payload=canonical_json(data)
    return {'schema':SCHEMA,'status':'independent_preview_only','ready_for_boq':False,
            'input_sha256':sha256(payload.encode('utf-8')).hexdigest(),
            'source_ref':m['source_ref'],'project_id':m['project_id'],
            'floor_id':m['floor_id'],'stair_id':m['stair_id'],
            'rows':sorted(rows,key=lambda r:(r['source_id'],r['operation'])),
            'component_calculations':sorted(formulas,key=lambda a:a['component']),
            'form_faces':sorted(face_details,key=lambda a:a['key']),
            'limitations':['rectangular aligned footprints; positive-rise straight flights only',
              'exactly full-depth interior rectangular voids; signed reveal form area',
              'independent triangular steps ONLY under explicit exclusion above waist',
              'plan-overlap screening conservative; not a complete 3D clash model',
              'connections are shared boundaries without additional paid concrete',
              'no automatic design, code-based bar development, BOQ, SQLite or Windows acceptance']}
