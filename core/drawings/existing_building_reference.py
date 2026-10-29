"""Safe display-only existing-building IFC2X3 legacy reference for renovation review.

Not an engineering IFC4 BIMAdapter conversion and never a source of QTO,
BOQ, changes, payment, retrofit approval or inferred building status.
"""
from __future__ import annotations
from pathlib import Path
import math
from core.drawings.site_context import file_digest, SiteTerrainScene, MAX_TRIANGLES


class ExistingBuildingReferenceScene(SiteTerrainScene):
    def __init__(self, *, source_path, source_sha256, revision, vertices, triangles,
                 source_member_count, source_with_geometry_count,
                 displayed_source_global_id, displayed_ifc_type):
        super().__init__(source_path=source_path,source_sha256=source_sha256,
                         revision=revision,site_global_id=None,site_identity_canonical=False,
                         vertices=vertices,triangles=triangles)
        self.display_kind="IFC2X3-existing-building-visual-only"
        self.source_member_count=source_member_count
        self.source_with_geometry_count=source_with_geometry_count
        self.displayed_source_global_id=displayed_source_global_id
        self.displayed_ifc_type=displayed_ifc_type
        self.element_global_ids=frozenset()  # deliberately no authorized member IDs
        self.member_identity_linkable=False
        self.renovation_phases_verified=False
        self.explicit_quantity_authority=False


def verified_existing_reference(path, *, revision, expected_sha256, max_triangles=MAX_TRIANGLES):
    import ifcopenshell
    import ifcopenshell.geom
    if not isinstance(revision,str) or not revision.strip():
        raise ValueError("Revision منبع وضع موجود الزامی است.")
    if type(max_triangles) is not int or not 1<=max_triangles<=MAX_TRIANGLES:
        raise ValueError("حد نمایش هندسه وضع موجود نامعتبر است.")
    path=Path(path)
    if not path.is_file() or path.suffix.lower()!=".ifc":
        raise ValueError("فایل IFC وضع موجود قابل‌خواندن نیست.")
    before=file_digest(path)
    if before!=expected_sha256:
        raise ValueError("SHA منبع وضع موجود با درخواست تطبیق ندارد.")
    source=ifcopenshell.open(str(path))
    if str(source.schema)!="IFC2X3" or len(source.by_type("IfcProject"))!=1:
        raise ValueError("این مسیر صرفاً نمایش وضعیت موجود IFC2X3 است.")
    elems=source.by_type("IfcElement")
    ids=[str(getattr(x,"GlobalId","") or "") for x in elems]
    if not elems or not all(ids) or len(ids)!=len(set(ids)):
        raise ValueError("فهرست اعضای وضع موجود خالی یا تکراری است.")
    units=source.by_type("IfcProject")[0].UnitsInContext
    if len([u for u in getattr(units,"Units",()) if getattr(u,"UnitType",None)=="LENGTHUNIT"])!=1:
        raise ValueError("واحد طول وضع موجود یکتا نیست.")
    candidates=[x for x in elems if getattr(x,"Representation",None)]
    candidates.sort(key=lambda x:(0 if x.is_a()=="IfcWall" else 1,x.GlobalId))
    if not candidates:
        raise ValueError("مدل وضع موجود فاقد هندسهٔ صریح است.")
    settings=ifcopenshell.geom.settings()
    settings.set("use-world-coords",True)
    failures=0
    for obj in candidates[:48]:
        try:
            shape=ifcopenshell.geom.create_shape(settings,obj)
            v=tuple(shape.geometry.verts)
            f=tuple(shape.geometry.faces)
            if not v or len(v)%3 or not f or len(f)%3 or len(f)//3>max_triangles:
                failures+=1
                continue
            if any(not math.isfinite(x) or abs(x)>1e12 for x in v):
                failures+=1
                continue
            vertices=tuple(tuple(v[i:i+3]) for i in range(0,len(v),3))
            triangles=tuple(tuple(f[i:i+3]) for i in range(0,len(f),3))
            if any(len(set(t))!=3 or any(type(j) is not int or j<0 or j>=len(vertices) for j in t)
                   for t in triangles):
                failures+=1
                continue
            if file_digest(path)!=before:
                raise ValueError("مدل وضع موجود هنگام بارگذاری تغییر کرده است.")
            return ExistingBuildingReferenceScene(
                source_path=str(path),source_sha256=before,revision=revision,
                vertices=vertices,triangles=triangles,
                source_member_count=len(elems),source_with_geometry_count=len(candidates),
                displayed_source_global_id=obj.GlobalId,displayed_ifc_type=obj.is_a())
        except (RuntimeError,TypeError):
            failures+=1
            continue
    raise ValueError("هیچ هندسهٔ قابل نمایش در محدودهٔ بررسی ایمن وجود ندارد؛ منبع رد شد.")
