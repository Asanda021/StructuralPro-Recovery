"""Offline CAD takeoff engine with layer/block/xref aware extraction."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import math
import hashlib
import io


@dataclass(frozen=True)
class DWGEntity:
    entity_type: str
    layer: str
    handle: str | None
    data: dict[str, Any]


@dataclass
class DWGDocument:
    entities: list[DWGEntity] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    block_counts: dict[str, int] = field(default_factory=dict)
    text_labels: list[str] = field(default_factory=list)
    xrefs: list[str] = field(default_factory=list)
    units: str = "unknown"
    source: str = ""
    format: str = "DXF"
    source_sha256: str = ""
    dxf_version: str = ""
    warnings: list[str] = field(default_factory=list)
    conversion: dict[str, Any] = field(default_factory=dict)


def _xy(v):
    result=(float(v[0]),float(v[1]))
    if not all(math.isfinite(x) for x in result):raise ValueError("مختصات CAD باید متناهی باشند")
    return result


_UNIT_FACTORS = {"in": 0.0254, "ft": 0.3048, "mi": 1609.344, "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}


def cad_unit_factor(unit: str) -> float | None:
    """Return multiplier from a known CAD unit to canonical metres."""
    return _UNIT_FACTORS.get(str(unit or "unknown").lower())


def _poly_metrics(points, closed=False, bulges=None):
    pts = [_xy(p) for p in points]
    if any(not math.isfinite(v) for p in pts for v in p):
        raise ValueError("CAD geometry contains non-finite coordinates")
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    if closed and len(pts) > 2:
        length += math.dist(pts[-1], pts[0])
    area = 0.0
    if len(pts) > 2 and closed:
        area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2)
    if closed and len(pts)>2 and not any(bulges or []):
        from core.drawings.planar_geometry import ring,signed,decimal_text
        area=float(decimal_text(abs(signed(ring(pts)))))
    if bulges is not None:
        signed_area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                          - pts[(i + 1) % len(pts)][0] * pts[i][1]
                          for i in range(len(pts))) / 2 if closed and len(pts) > 2 else 0.0
        # DXF bulge is tan(signed sweep / 4); use the actual circular arc,
        # never its chord, for engineering length and enclosed area.
        for i in range(len(pts) if closed else max(0, len(pts) - 1)):
            bulge = float(bulges[i])
            if not math.isfinite(bulge):
                raise ValueError("CAD bulge must be finite")
            if bulge == 0:
                continue
            chord = math.dist(pts[i], pts[(i + 1) % len(pts)])
            if chord == 0:
                raise ValueError("CAD arc has coincident endpoints")
            sweep = 4 * math.atan(bulge)
            radius = chord / (2 * abs(math.sin(sweep / 2)))
            length += radius * abs(sweep) - chord
            signed_area += radius * radius * (sweep - math.sin(sweep)) / 2
        if any(bulges):area = abs(signed_area) if closed else 0.0
    if not math.isfinite(length) or not math.isfinite(area):
        raise ValueError("CAD geometry result must be finite")
    return length, area


def _expanded_entities(entities,document,warnings,path=(),names=(),inherited=None,budget=None,parent_visible=True):
    """Expand real INSERT transforms with bounded depth and auditable handle paths."""
    budget=budget if budget is not None else [0]
    for index,e in enumerate(entities):
        original=e.origin_of_copy if e.is_virtual else e
        handle=str(getattr(original.dxf,'handle','') or '')
        if not handle:raise ValueError('هویت Handle جزء CAD موجود نیست')
        identity=path+(handle,)
        layer=str(e.dxf.layer)
        if layer=='0' and inherited:layer=inherited
        budget[0]+=1
        if budget[0]>250000:raise ValueError('تعداد اجزای بازشده از حد ۲۵۰۰۰۰ بیشتر است؛ پردازش متوقف شد')
        layer_record=document.layers.get(layer) if layer in document.layers else None
        visible=parent_visible and not bool(e.dxf.get('invisible',0)) and (layer_record is None or not(layer_record.is_off() or layer_record.is_frozen()))
        yield e,'/'.join(identity),layer,visible
        if e.dxftype()=='INSERT':
            if e.mcount>1:raise ValueError('آرایه MINSERT خارج از قرارداد فعلی است؛ حذف خاموش نمونه‌ها مجاز نیست')
            name=e.dxf.name
            if name in names or len(names)>=32:raise ValueError('چرخه یا عمق نامعتبر بلوک CAD')
            block=document.blocks.get(name)
            if block is None:raise ValueError('مرجع بلوک CAD یافت نشد')
            if block.block.is_xref or block.block.is_xref_overlay:
                warnings.append('XREF حل‌نشده: '+name);continue
            skipped=[]
            virtual=list(e.virtual_entities(skipped_entity_callback=lambda entity,reason:skipped.append(str(reason))))
            if skipped:raise ValueError('تبدیل کامل اجزای بلوک ممکن نیست: '+'؛ '.join(skipped))
            yield from _expanded_entities(virtual,document,warnings,identity,names+(name,),layer,budget,visible)


def _nonplanar(e):
    d=e.dxf;typ=e.dxftype()
    values=[]
    if typ=='LINE':values=[d.start.z,d.end.z]
    elif typ in ('CIRCLE','ARC'):values=[d.center.z]
    elif typ=='LWPOLYLINE':values=[d.elevation]
    elif typ=='POLYLINE':values=[v.dxf.location.z for v in e.vertices]+[d.elevation.z]
    extrusion=d.get('extrusion',(0,0,1))
    return any(not math.isfinite(float(v)) or float(v)!=0 for v in values) or tuple(extrusion)!=(0,0,1)


class DWGTakeoffEngine:
    def _read_dxf(self, p: Path) -> DWGDocument:
        try:
            import ezdxf
        except ImportError as exc:
            raise RuntimeError(
                "کتابخانه ezdxf برای تحلیل DXF نصب نیست؛ نصب وابستگی‌های StructuralPro را بررسی کنید."
            ) from exc

        source_bytes=p.read_bytes();fingerprint=hashlib.sha256(source_bytes).hexdigest()
        if not source_bytes.startswith(b'AutoCAD Binary DXF'):
            stream=io.BytesIO(source_bytes);handles=set()
            while True:
                code=stream.readline()
                if not code:break
                value=stream.readline().strip()
                if code.strip() in (b'5',b'105'):
                    if value in handles:raise RuntimeError('Handle تکراری در بایت منبع DXF؛ اصلاح خاموش هویت مجاز نیست')
                    handles.add(value)
        try:
            doc = ezdxf.readfile(str(p))
        except Exception as exc:
            raise RuntimeError(
                f"خواندن فایل CAD شکست خورد؛ فایل ممکن است خراب یا با نسخه/ساختار غیرقابل‌خواندن باشد: {exc}"
            ) from exc

        out = DWGDocument(source=str(p), format="DXF",source_sha256=fingerprint,dxf_version=doc.dxfversion)
        layers = set()
        units_map = {0: "unitless", 1: "in", 2: "ft", 3: "mi", 4: "mm", 5: "cm", 6: "m", 7: "km"}
        raw_units = int(doc.header.get("$INSUNITS", 0) or 0)
        out.units = units_map.get(raw_units, "unknown")
        out.__dict__["unit_name"] = out.units
        try:
            out.xrefs = [str(x) for x in doc.xrefdocpaths]
        except Exception:
            pass

        try:
            entities = doc.modelspace()
            for e,entity_handle,layer,source_visible in _expanded_entities(entities,doc,out.warnings):
                typ = e.dxftype()
                layers.add(layer)
                data = {}

                if typ == "LINE":
                    data["start"] = _xy(e.dxf.start)
                    data["end"] = _xy(e.dxf.end)
                    data["length"] = math.dist(data["start"], data["end"])
                elif typ == "POLYLINE" and (e.is_polygon_mesh or e.is_poly_face_mesh):
                    # Mesh topology is not a 2D polyline. Keep its provenance and
                    # vertices, but never fabricate chord lengths or planar area.
                    data["mesh_vertices"] = [tuple(float(c) for c in v.dxf.location) for v in e.vertices]
                    data["unsupported_measurement"] = "شبکه سه‌بعدی به متره سطحی دوبعدی تبدیل نمی‌شود"
                elif typ in {"LWPOLYLINE", "POLYLINE"}:
                    pts = [_xy(p) for p in e.get_points("xy")] if typ == "LWPOLYLINE" else [_xy(v.dxf.location) for v in e.vertices]
                    bulges = [p[2] for p in e.get_points("xyb")] if typ == "LWPOLYLINE" else [float(getattr(v.dxf, "bulge", 0)) for v in e.vertices]
                    data["length"], data["area"] = _poly_metrics(pts, bool(getattr(e, "is_closed", getattr(e, "closed", False))), bulges)
                    data["points"] = pts
                    data["bulges"] = bulges
                elif typ == "CIRCLE":
                    r = float(e.dxf.radius)
                    data.update(radius=r, length=2 * math.pi * r, area=math.pi * r * r)
                elif typ == "ARC":
                    r = float(e.dxf.radius)
                    sweep = (float(e.dxf.end_angle) - float(e.dxf.start_angle)) % 360
                    data.update(radius=r, length=2 * math.pi * r * sweep / 360)
                elif typ in {"TEXT", "MTEXT"}:
                    data["text"] = str(e.dxf.text if hasattr(e.dxf, "text") else e.text)
                    data["insert"] = _xy(e.dxf.insert)
                    data["height"] = float(getattr(e.dxf, "height", getattr(e.dxf, "char_height", 1)))
                    data["rotation"]=float(e.get_rotation() if typ=="MTEXT" else e.dxf.rotation)
                    style=doc.styles.get(e.dxf.style) if e.dxf.style in doc.styles else None
                    data["font_name"]=str(style.dxf.font) if style else "unknown"
                    data["font_notice"]="نمایش با فونت سیستم جایگزین؛ تطبیق SHX و چیدمان اصلی تأیید نشده"
                    out.text_labels.append(data["text"])
                elif typ == "INSERT":
                    name = str(e.dxf.name)
                    out.block_counts[name] = out.block_counts.get(name, 0) + 1
                    data.update(block=name, insert=_xy(e.dxf.insert),rotation=float(e.dxf.rotation),scale=tuple(float(e.dxf.get(k,1)) for k in ("xscale","yscale","zscale")),unsupported_measurement="بلوک مالک محاسبه جدا از اجزای بازشده نیست")
                elif typ == "HATCH":
                    data["pattern"] = str(getattr(e.dxf, "pattern_name", ""))
                else:
                    for attr in ("start", "end", "center", "insert"):
                        if hasattr(e.dxf, attr):
                            try:
                                data[attr] = _xy(getattr(e.dxf, attr))
                            except Exception:
                                pass

                if typ in {"CIRCLE", "ARC"}:
                    data["center"] = _xy(e.dxf.center)
                if typ in {"LWPOLYLINE", "POLYLINE", "ARC"} and not data.get("unsupported_measurement"):
                    from ezdxf.path import make_path
                    path = make_path(e)
                    control = list(path.control_vertices())
                    span = max((max(p.x for p in control) - min(p.x for p in control)),
                               (max(p.y for p in control) - min(p.y for p in control)), 1e-6)
                    # Display approximation only; takeoff uses analytic metrics above.
                    display = []
                    for point in path.flattening(distance=span * 1e-4):
                        display.append(_xy(point))
                        if len(display) > 20000:
                            raise ValueError("هندسه CAD برای نمایش بسیار پیچیده است")
                    data["display_points"] = display
                    data["closed"] = bool(path.is_closed)
                if _nonplanar(e):
                    data.setdefault("unsupported_measurement","هندسه دارای Z یا صفحه غیر XY؛ متره دوبعدی مسدود است")
                    data.pop("length",None);data.pop("area",None)
                if typ not in {"LINE","POLYLINE","LWPOLYLINE","CIRCLE","ARC","TEXT","MTEXT","INSERT"}:data["unsupported_measurement"]="نوع جزء برای متره مستقیم پشتیبانی نشده: "+typ
                if not all(math.isfinite(float(data[k])) and float(data[k])>=0 for k in ("length","area","radius","height") if k in data):raise ValueError("مقدار هندسی CAD نامعتبر است")
                data["handle_path"]=entity_handle;data["original_layer"]=str(e.dxf.layer)
                layer_record=doc.layers.get(layer) if layer in doc.layers else None
                if layer_record is None:
                    out.warnings.append("لایه در جدول منبع تعریف نشده: "+layer)
                data["layer_defined"]=layer_record is not None
                data["layer_visible"]=source_visible
                out.entities.append(DWGEntity(typ, layer, entity_handle, data))
        except Exception as exc:
            raise RuntimeError(f"تحلیل عناصر CAD شکست خورد: {exc}") from exc

        factor = cad_unit_factor(out.units)
        if factor is not None and factor != 1.0:
            normalized = []
            for entity in out.entities:
                data = dict(entity.data)
                for key in ("length", "radius", "height"):
                    if key in data:
                        data[key] = float(data[key]) * factor
                if "area" in data:
                    data["area"] = float(data["area"]) * (factor ** 2)
                for key in ("start", "end", "insert", "center"):
                    if key in data and data[key] is not None:
                        data[key] = (float(data[key][0]) * factor, float(data[key][1]) * factor)
                if "points" in data:
                    data["points"] = [(float(p[0]) * factor, float(p[1]) * factor) for p in data["points"]]
                if "display_points" in data:
                    data["display_points"] = [(float(p[0]) * factor, float(p[1]) * factor) for p in data["display_points"]]
                normalized.append(DWGEntity(entity.entity_type, entity.layer, entity.handle, data))
            out.entities = normalized

        if hashlib.sha256(p.read_bytes()).hexdigest()!=fingerprint:raise RuntimeError("فایل CAD هنگام خواندن تغییر کرده است")
        out.layers = sorted(layers)
        return out

    def import_file(self, path: str | Path) -> DWGDocument:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"فایل CAD پیدا نشد: {p}")
        if not p.is_file():
            raise ValueError(f"مسیر CAD یک فایل نیست: {p}")
        if p.suffix.lower() == ".dxf":
            return self._read_dxf(p)
        if p.suffix.lower() != ".dwg":
            raise ValueError("فرمت فایل باید DWG یا DXF باشد.")

        original_sha=hashlib.sha256(p.read_bytes()).hexdigest()
        # Prefer the bundled/authorized ACadSharp bridge used by the Windows
        # product. Use a separately installed offline converter only when that
        # bridge is genuinely unavailable; conversion failures from an available
        # bridge must remain visible rather than silently switching backends.
        from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider
        provider = ACadSharpDWGProvider()
        if provider.available:
            converted = provider.convert(p)
            try:
                doc = self._read_dxf(converted)
            finally:
                converted.unlink(missing_ok=True)
            doc.conversion={"provider":"ACadSharp bridge","source_sha256":original_sha,"output_sha256":doc.source_sha256,"decoder_version":getattr(provider,"version","unverified"),"exit_code":0}
            if hashlib.sha256(p.read_bytes()).hexdigest()!=original_sha:raise RuntimeError("فایل DWG هنگام تبدیل تغییر کرده است")
            doc.source_sha256=original_sha
            doc.source = str(p)
            doc.format = "DWG→DXF (ACadSharp)"
            return doc

        from core.drawings.dwg_converter import OfflineDWGConverter
        result = OfflineDWGConverter().convert(p)
        try:
            doc = self._read_dxf(result.output)
        finally:
            result.output.unlink(missing_ok=True)
            if result.output.parent.name.startswith("structuralpro_dwg_"):
                try:
                    result.output.parent.rmdir()
                except OSError:
                    pass
        doc.conversion={"provider":result.converter,"source_sha256":result.source_sha256,"output_sha256":result.output_sha256,"dwg_version":result.dwg_version,"exit_code":result.exit_code}
        doc.source_sha256=original_sha
        doc.source = str(p)
        doc.format = "DWG→DXF (offline converter)"
        return doc

    def summarize(self, doc: DWGDocument) -> dict[str, Any]:
        by_type = {}
        for e in doc.entities:
            by_type[e.entity_type] = by_type.get(e.entity_type, 0) + 1
        return {
            "entities": len(doc.entities),
            "by_type": by_type,
            "layers": doc.layers,
            "blocks": doc.block_counts,
            "text_count": len(doc.text_labels),
            "xrefs": doc.xrefs,
            "units": doc.units,
            "source": doc.source,
            "source_sha256":doc.source_sha256,"dxf_version":doc.dxf_version,"warnings":doc.warnings,"conversion":doc.conversion,
            "format": doc.format,
            "unsupported_geometry_count": sum(bool(e.data.get("unsupported_measurement")) for e in doc.entities),
        }

    def layer_takeoff(self, doc: DWGDocument, rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Create review-required layer summaries; never treat raw/unknown units as metres."""
        out = []
        for layer, rule in rules.items():
            ents = [e for e in doc.entities if e.layer == layer]
            if not ents:
                continue
            metric = str(rule.get("metric", "count")).strip().lower()
            if metric not in {"count", "length", "area"}:
                raise ValueError(f"متریک CAD پشتیبانی نمی‌شود: {metric}")
            if metric in {"length", "area"} and cad_unit_factor(doc.units) is None:
                raise ValueError(
                    f"واحد نقشه CAD برای لایه {layer} نامشخص است؛ پیش از برداشت طول/مساحت، واحد یا کالیبراسیون معتبر تعیین شود."
                )
            values = []
            parent_paths={e.handle.rsplit("/",1)[0] for e in ents if e.handle and "/" in e.handle}
            if metric=="count" and any(e.entity_type=="INSERT" and e.handle in parent_paths for e in ents):raise ValueError("شمارش هم‌زمان بلوک و اجزای آن نیازمند قرارداد مستقل است")
            if any(e.data.get("layer_visible") is False for e in ents):raise ValueError("لایه یا جزء پنهان برای متره نیازمند بازبینی مستقل است")
            for entity in ents:
                if metric != "count" and entity.data.get("unsupported_measurement"):
                    raise ValueError(entity.data["unsupported_measurement"])
                raw = entity.data.get(metric, 1 if metric == "count" else None)
                if raw is None:
                    raise ValueError(f"هندسه لازم برای متریک {metric} در لایه {layer} وجود ندارد.")
                value = float(raw)
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"مقدار CAD نامعتبر در لایه: {layer}")
                values.append(value)
            qty = sum(values)
            default_unit = {"count": "عدد", "length": "m", "area": "m²"}[metric]
            out.append({
                "layer": layer,
                "count": len(ents),
                "quantity": qty,
                "description": str(rule.get("description", layer)),
                "unit": str(rule.get("unit", default_unit)),
                "price_code": rule.get("price_code"),
                "source": f"dwg-layer:{layer}",
                "needs_confirmation": True,
                "unit_basis": doc.units,
                "metric": metric,
            })
        return out

def infer_takeoff_from_layers(doc: DWGDocument, rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return DWGTakeoffEngine().layer_takeoff(doc, rules)


def cad_entity_geometry(document,handle,metric,origin=(0,0)):
    """Bounded direct-entity contract: straight XY linework only; no material inference."""
    if cad_unit_factor(document.units) is None:raise ValueError('واحد CAD نامشخص است')
    found=[e for e in document.entities if e.handle==handle]
    if len(found)!=1:raise ValueError('Handle یکتا و معتبر لازم است')
    e=found[0];d=e.data
    if d.get('unsupported_measurement') or d.get('layer_visible') is False or d.get('layer_defined') is False:raise ValueError('جزء پنهان یا فاقد قرارداد متره مستقیم است')
    if e.entity_type=='LINE':points=[d['start'],d['end']]
    elif e.entity_type in {'POLYLINE','LWPOLYLINE'} and not any(d.get('bulges',[])):points=d['points']
    else:raise ValueError('ثبت مستقیم فعلاً فقط خط و چندخطی مستقیم XY را می‌پذیرد؛ منحنی نیازمند قرارداد مستقل است')
    if metric not in {'length','area'} or (metric=='area' and not d.get('closed')):raise ValueError('سطح نیازمند حلقه بسته معتبر است')
    if metric=='length' and d.get('closed'):points=points+[points[0]]
    ox,oy=(float(v) for v in origin)
    if not all(math.isfinite(v) for v in (ox,oy)):raise ValueError('مبدأ نمایش نامعتبر است')
    return e,[(float(x)-ox,oy-float(y)) for x,y in points],float(d[metric])


def cad_review_digest(item):
    import json
    value=item.to_dict();value['cad_evidence']=dict(value['cad_evidence']);value['cad_evidence'].pop('review',None)
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_cad_item(item,document,*,require_review=True):
    meta=item.cad_evidence
    if not isinstance(meta,dict) or meta.get('policy')!='cad_entity_review_v1':raise ValueError('قرارداد منشأ CAD معتبر نیست')
    if meta.get('source_sha256')!=document.source_sha256 or meta.get('unit_basis')!=document.units or meta.get('unit_factor_to_m')!=str(cad_unit_factor(document.units)) or meta.get('dxf_version')!=document.dxf_version:raise ValueError('منبع یا واحد CAD تغییر کرده است')
    if any(meta.get('conversion',{}).get(k)!=document.conversion.get(k) for k in ('provider','decoder_version')):raise ValueError('Decoder مبنای بازبینی تغییر کرده است')
    e,points,amount=cad_entity_geometry(document,meta.get('handle'),item.kind,meta.get('scene_origin',()))
    if e.layer!=meta.get('layer') or tuple(map(tuple,points))!=item.geometry or item.holes or not math.isclose(amount,item.quantity,rel_tol=1e-12,abs_tol=0):raise ValueError('مقدار یا هندسه متره با جزء اصلی CAD مطابق نیست')
    if any(not str(meta.get(k,'')).strip() for k in ('floor_id','member_id','quantity_owner','created_by','reference')):raise ValueError('طبقه، عضو، مالک، سازنده و مدرک CAD الزامی است')
    if item.kind=="area" and any((item.geometry_evidence or {}).get(k)!=meta.get(k) for k in ("floor_id","member_id","quantity_owner")):raise ValueError("مالکیت هندسه و جزء CAD یکسان نیست")
    if require_review:
        if document.format.startswith("DWG") and document.conversion.get("decoder_version") in {None,"unverified"}:raise ValueError("نسخه Decoder معتبر DWG برای ثبت قطعی گزارش نشده است")
        from core.projects.project_model import _identity
        review=meta.get('review') or {}
        if not str(review.get('note','')).strip() or not str(review.get('reviewer','')).strip() or _identity(review['reviewer']).casefold()==_identity(meta['created_by']).casefold() or review.get('digest')!=cad_review_digest(item):raise ValueError('بازبینی مستقل و جاری CAD لازم است')
    return e
