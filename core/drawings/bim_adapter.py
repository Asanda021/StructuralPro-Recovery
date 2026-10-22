from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class BIMObject:
    global_id: str
    ifc_type: str
    name: str
    properties: dict[str, Any]

class BIMAdapter:
    def read_ifc(self, path: str | Path) -> list[BIMObject]:
        p=Path(path)
        if not p.exists(): raise FileNotFoundError(p)
        try: import ifcopenshell
        except ImportError as exc: raise RuntimeError("Install ifcopenshell to read IFC offline") from exc
        model=ifcopenshell.open(str(p)); objects=[]
        for obj in model.by_type("IfcProduct"):
            objects.append(BIMObject(obj.GlobalId,obj.is_a(),getattr(obj,"Name",None) or "",{"ObjectType":getattr(obj,"ObjectType",None)}))
        return objects
    @staticmethod
    def count_by_type(objects: list[BIMObject]) -> dict[str,int]:
        out={}
        for obj in objects: out[obj.ifc_type]=out.get(obj.ifc_type,0)+1
        return out

    def read_document(self, path: str | Path, *, revision: str) -> dict[str, Any]:
        """IFC4 engineering evidence, separate from tessellated display quantities.

        QTO values retain STEP decimal scalars; placement uses parser scalars. No mesh,
        bounding box, material quantity or ownership is inferred. Only SI units
        and rigid local placements are supported here; map conversion is retained
        as an explicit crosswalk blocker.
        """
        from decimal import Decimal, localcontext
        from hashlib import sha256
        p=Path(path)
        if not isinstance(revision,str) or not revision.strip():
            raise ValueError('Revision منبع IFC الزامی است')
        raw=p.read_bytes()
        if not raw:raise ValueError('فایل IFC خالی است')
        try:
            import ifcopenshell
        except ImportError as exc:
            raise RuntimeError('برای خواندن IFC، IfcOpenShell محلی لازم است') from exc
        try:
            model=ifcopenshell.file.from_string(raw.decode('utf-8-sig'))
            schema=model.schema
        except Exception as exc:raise ValueError('خواندن فایل IFC شکست خورد') from exc
        if schema!='IFC4':raise ValueError('Schema خارج از قرارداد آزموده‌شده IFC4 است')
        projects=model.by_type('IfcProject')
        if len(projects)!=1:raise ValueError('مدل باید دقیقاً یک پروژه IFC داشته باشد')
        seen=set()
        for root in model.by_type('IfcRoot'):
            gid=getattr(root,'GlobalId',None)
            if not gid or not isinstance(gid,str) or len(gid)!=22:
                raise ValueError('GlobalId باید معتبر و صریح باشد')
            try:ifcopenshell.guid.expand(gid)
            except Exception as exc:raise ValueError('GlobalId نامعتبر است') from exc
            if gid in seen:raise ValueError('GlobalId تکراری است: '+gid)
            seen.add(gid)
        # IfcOpenShell exposes IFC REAL values as binary doubles. Preserve the
        # literal QTO scalar by its parser-validated STEP entity id; this is a
        # lexical evidence reader, not a second IFC semantic/geometry parser.
        import re
        source_text=raw.decode('utf-8-sig');literals={};i=0
        quantity_pattern=re.compile(r"#([0-9]+)\s*=\s*(IFCQUANTITY(?:LENGTH|AREA|VOLUME|COUNT))\s*\(",re.I)
        def quoted_end(text,start):
            k=start+1
            while k<len(text):
                if text[k]=="'":
                    if k+1<len(text) and text[k+1]=="'":k+=2;continue
                    return k+1
                k+=1
            raise ValueError('رشته STEP ناقص است')
        while i<len(source_text):
            if source_text[i]=="'":i=quoted_end(source_text,i);continue
            if source_text.startswith('/*',i):
                end=source_text.find('*/',i+2)
                if end<0:raise ValueError('توضیح STEP ناقص است')
                i=end+2;continue
            match=quantity_pattern.match(source_text,i) if source_text[i]=='#' else None
            if not match:i+=1;continue
            start=k=match.end();depth=0;args=[]
            while k<len(source_text):
                char=source_text[k]
                if char=="'":k=quoted_end(source_text,k);continue
                if char=='(':depth+=1
                elif char==')':
                    if depth==0:
                        args.append(source_text[start:k].strip());break
                    depth-=1
                elif char==',' and depth==0:args.append(source_text[start:k].strip());start=k+1
                k+=1
            if k>=len(source_text) or len(args)<4:raise ValueError('اسکالر مستند کمیت IFC ناقص است')
            sid=int(match.group(1))
            if sid in literals:raise ValueError('شناسه STEP کمیت تکراری است')
            literals[sid]=(match.group(2).upper(),args[3]);i=k+1
        project=projects[0]
        prefixes={None:Decimal(1),'MILLI':Decimal('.001'),'CENTI':Decimal('.01'),'DECI':Decimal('.1'),'KILO':Decimal(1000),'MICRO':Decimal('.000001')}
        types={'LENGTHUNIT':('METRE',1,'m'),'AREAUNIT':('SQUARE_METRE',2,'m2'),'VOLUMEUNIT':('CUBIC_METRE',3,'m3')}
        def number(v,label):
            try:d=Decimal(str(v))
            except Exception as exc:raise ValueError(label+' نامعتبر است') from exc
            if not d.is_finite() or abs(d)>Decimal('1e30'):raise ValueError(label+' خارج از دامنه عددی است')
            return d
        def unit_factor(u,kind):
            expected,power,_=types[kind]
            if not u.is_a('IfcSIUnit') or u.UnitType!=kind or u.Name!=expected or u.Prefix not in prefixes:
                raise ValueError('واحد IFC خارج از قرارداد SI معتبر است')
            return prefixes[u.Prefix]**power
        units={}
        for u in getattr(getattr(project,'UnitsInContext',None),'Units',()) or ():
            kind=getattr(u,'UnitType',None)
            if kind in types:
                if kind in units:raise ValueError('نوع واحد IFC تکراری است')
                units[kind]=unit_factor(u,kind)
        if 'LENGTHUNIT' not in units:raise ValueError('واحد طول IFC نامشخص است')
        units.setdefault('AREAUNIT',units['LENGTHUNIT']**2)
        units.setdefault('VOLUMEUNIT',units['LENGTHUNIT']**3)
        I=tuple(tuple(Decimal(i==j) for j in range(4)) for i in range(4))
        cache={};active=set()
        def vector(entity,default):
            a=tuple(number(x,'جهت محور') for x in entity.DirectionRatios) if entity else default
            if len(a)!=3:raise ValueError('جهت محور سه‌بعدی معتبر نیست')
            n=sum(x*x for x in a).sqrt()
            if not n:raise ValueError('جهت محور صفر است')
            return tuple(x/n for x in a)
        def placement(pl,depth=0):
            if pl is None:return I
            if depth>64 or pl.id() in active:raise ValueError('چرخه یا عمق نامعتبر Placement')
            if pl.id() in cache:return cache[pl.id()]
            if not pl.is_a('IfcLocalPlacement'):raise ValueError('نوع Placement پشتیبانی نمی‌شود')
            active.add(pl.id())
            r=pl.RelativePlacement
            if not r.is_a('IfcAxis2Placement3D'):raise ValueError('Placement باید سه‌بعدی صریح باشد')
            pos=tuple(number(x,'مختصات')*units['LENGTHUNIT'] for x in r.Location.Coordinates)
            if len(pos)!=3 or any(abs(x)>Decimal('1e12') for x in pos):raise ValueError('مختصات خارج از دامنه معتبر است')
            z=vector(r.Axis,(Decimal(0),Decimal(0),Decimal(1)))
            x=vector(r.RefDirection,(Decimal(1),Decimal(0),Decimal(0)))
            if abs(sum(a*b for a,b in zip(x,z)))>Decimal('1e-24'):raise ValueError('جهت محورهای Placement متعامد نیست')
            y=(z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0])
            local=tuple(tuple((x[i],y[i],z[i],pos[i])) for i in range(3))+((Decimal(0),Decimal(0),Decimal(0),Decimal(1)),)
            parent=placement(pl.PlacementRelTo,depth+1)
            matrix=tuple(tuple(sum(parent[i][k]*local[k][j] for k in range(4)) for j in range(4)) for i in range(4))
            if any(abs(matrix[i][3])>Decimal('1e12') for i in range(3)):raise ValueError('مختصات جهانی خارج از دامنه معتبر است')
            active.remove(pl.id());cache[pl.id()]=matrix;return matrix
        def hierarchy(obj):
            chain=[];visited=set();cur=obj
            while cur is not None:
                if cur.id() in visited or len(chain)>64:raise ValueError('چرخه رابطه فضایی IFC')
                visited.add(cur.id());chain.append(cur)
                rels=list(getattr(cur,'Decomposes',()) or ())
                if len(rels)>1:raise ValueError('رابطه فضایی مبهم است')
                cur=rels[0].RelatingObject if rels else None
            return chain
        def spatial(obj):
            rels=list(getattr(obj,'ContainedInStructure',()) or ())
            if len(rels)>1:raise ValueError('عضویت فضایی متناقض است')
            if not rels:return None,None,'فاقد طبقه؛ تطبیق بازبینی‌شده لازم است'
            chain=hierarchy(rels[0].RelatingStructure)
            storeys=[x for x in chain if x.is_a('IfcBuildingStorey')]
            buildings=[x for x in chain if x.is_a('IfcBuilding')]
            if len(storeys)!=1 or len(buildings)!=1 or project not in chain:
                return None,None,'سلسله‌مراتب فضایی کامل و یکتا نیست'
            return storeys[0].GlobalId,buildings[0].GlobalId,''
        with localcontext() as ctx:
            ctx.prec=80
            storeys=[]
            for st in sorted(model.by_type('IfcBuildingStorey'),key=lambda x:x.id()):
                mat=placement(st.ObjectPlacement)
                storeys.append({'global_id':st.GlobalId,'name':st.Name or '',
                    'elevation_m':str(number(st.Elevation,'تراز')*units['LENGTHUNIT']) if st.Elevation is not None else None,
                    'origin_m':[str(mat[i][3]) for i in range(3)]})
            elements=[]
            fields={'IfcQuantityLength':('LengthValue','LENGTHUNIT','m'),
                    'IfcQuantityArea':('AreaValue','AREAUNIT','m2'),
                    'IfcQuantityVolume':('VolumeValue','VOLUMEUNIT','m3'),
                    'IfcQuantityCount':('CountValue',None,'عدد')}
            for obj in sorted(model.by_type('IfcElement'),key=lambda x:x.GlobalId):
                sid,bid,reason=spatial(obj);mat=placement(obj.ObjectPlacement);quantities=[];qnames=set();warnings=[]
                if obj.ObjectPlacement is None:warnings.append('Placement عضو موجود نیست؛ مبدأ قطعی نیست')
                for rel in getattr(obj,'IsDefinedBy',()) or ():
                    qset=getattr(rel,'RelatingPropertyDefinition',None)
                    if qset is None or not qset.is_a('IfcElementQuantity'):continue
                    for q in qset.Quantities:
                        name=q.Name or ''
                        if not name or name in qnames:raise ValueError('نام کمیت IFC خالی یا تکراری است')
                        qnames.add(name)
                        spec=fields.get(q.is_a())
                        if not spec:warnings.append('نوع کمیت فاقد قرارداد: '+q.is_a());continue
                        attr,kind,unit=spec
                        literal=literals.get(q.id())
                        if not literal or literal[0]!=q.is_a().upper():raise ValueError('اسکالر منبع کمیت IFC احراز نشد')
                        v=number(literal[1],'کمیت')
                        if len(v.as_tuple().digits)>64:raise ValueError('تعداد ارقام کمیت خارج از قرارداد دقیق است')
                        if float(v)!=getattr(q,attr):raise ValueError('اسکالر STEP با Parser کمیت تطابق ندارد')
                        if v<0:raise ValueError('کمیت منفی IFC مجاز نیست')
                        explicit=getattr(q,'Unit',None)
                        if kind is None:
                            if explicit is not None or v!=v.to_integral_value():raise ValueError('واحد یا تعداد صحیح کمیت نامعتبر است')
                            factor=Decimal(1)
                        else:factor=unit_factor(explicit,kind) if explicit else units[kind]
                        value=v*factor
                        if value and value.adjusted() < -24:raise ValueError('کمیت کمتر از حد دقت قرارداد است')
                        quantities.append({'name':name,'value_source':str(v),'value_si':str(value),'unit':unit,
                            'factor_to_si':str(factor),'source_kind':'explicit_qto','numeric_source':'STEP scalar bound to parser entity id','qset_id':qset.GlobalId,
                            'qset_name':qset.Name or '', 'step_id':q.id(),
                            'method':qset.MethodOfMeasurement or '',
                            'basis':'gross' if name.lower().startswith('gross') else 'net' if name.lower().startswith('net') else 'unspecified'})
                if reason:warnings.append(reason)
                elements.append({'global_id':obj.GlobalId,'ifc_type':obj.is_a(),'name':obj.Name or '',
                    'storey_id':sid,'building_id':bid,'origin_m':[str(mat[i][3]) for i in range(3)],
                    'placement_matrix_si':[[str(v) for v in row] for row in mat],
                    'placement_step_id':obj.ObjectPlacement.id() if obj.ObjectPlacement else None,
                    'quantities':quantities,'warnings':warnings,
                    'ready':False,'commit_allowed':False,'payable_rows':[]})
        if sha256(p.read_bytes()).digest()!=sha256(raw).digest():raise ValueError('فایل IFC حین پردازش تغییر کرده است')
        return {'policy':'ifc4_engineering_evidence_v1','source_path':str(p.resolve()),'source_sha256':sha256(raw).hexdigest(),
            'revision':revision.strip(),'source_id':'ifc:'+sha256(raw).hexdigest(),'schema':model.schema,
            'parser':'IfcOpenShell '+ifcopenshell.version,'project_id':project.GlobalId,'project_name':project.Name or '',
            'sites':[{'global_id':x.GlobalId,'name':x.Name or ''} for x in model.by_type('IfcSite')],
            'buildings':[{'global_id':x.GlobalId,'name':x.Name or ''} for x in model.by_type('IfcBuilding')],
            'unit_factors_si':{k:str(v) for k,v in units.items()},'storeys':storeys,'elements':elements,
            'map_conversion_supported':False,'map_conversion_present':bool(model.by_type('IfcMapConversion')),
            'numeric_policy':'Decimal80; exact QTO STEP scalars <=64 significant digits; placement over parser scalars; rigid placements <=1e12m; orthogonality 1e-24; minimum nonzero quantity 1e-24',
            'ready':False,'commit_allowed':False,'payable_rows':[]}
