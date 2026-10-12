"""Deep IFC adapter: identity, properties, materials, levels, types and quantities."""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import hashlib
import math
from .model import BIMElement

_TYPE_MAP={"IFCBEAM":("structural","beam"),"IFCCOLUMN":("structural","column"),
"IFCSLAB":("structural","slab"),"IFCWALL":("architectural","wall"),
"IFCFOOTING":("structural","foundation"),"IFCMEMBER":("structural","member"),
"IFCROOF":("architectural","roof"),"IFCWINDOW":("architectural","window"),
"IFCDOOR":("architectural","door")}

def _props(obj):
    out={}
    for definition in getattr(obj,"IsDefinedBy",()) or ():
        try:
            rel=definition.RelatingPropertyDefinition
            for prop in getattr(rel,"HasProperties",()) or ():
                name=str(getattr(prop,"Name","") or "")
                value=getattr(prop,"NominalValue",None)
                if value is not None:
                    out[name]=getattr(value,"wrappedValue",value)
        except Exception:
            continue
    return out

def _materials(obj):
    vals=[]
    for rel in getattr(obj,"HasAssociations",()) or ():
        mat=getattr(rel,"RelatingMaterial",None)
        if mat is None: continue
        for x in getattr(mat,"ForLayerSet",None).MaterialLayers if getattr(mat,"ForLayerSet",None) else ():
            vals.append(str(getattr(x.Material,"Name","") or ""))
        name=getattr(mat,"Name",None)
        if name: vals.append(str(name))
    return tuple(dict.fromkeys(x for x in vals if x))

def _level(obj):
    for rel in getattr(obj,"ContainedInStructure",()) or ():
        st=getattr(rel,"RelatingStructure",None)
        if st and str(st.is_a()).upper()=="IFCBUILDINGSTOREY":
            return str(getattr(st,"Name","") or "")
    return None

class DeepIFCAdapter:
    extensions=(".ifc",)
    def read_display_meshes(self, path, *, max_triangles=100_000):
        """World-coordinate meshes for display only; never quantity evidence."""
        if type(max_triangles) is not int or max_triangles <= 0:
            raise ValueError("ظرفیت نمایش باید عدد صحیح مثبت باشد.")
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        try:
            import ifcopenshell
            import ifcopenshell.geom
        except ImportError as exc:
            raise RuntimeError("برای نمایش مدل، وابستگی محلی ifcopenshell لازم است.") from exc
        raw = p.read_bytes()
        model = ifcopenshell.file.from_string(raw.decode("utf-8-sig"))
        projects = model.by_type("IfcProject")
        units = getattr(projects[0], "UnitsInContext", None) if len(projects) == 1 else None
        length_units = [u for u in getattr(units, "Units", ()) if getattr(u, "UnitType", None) == "LENGTHUNIT"]
        if len(length_units) != 1:
            raise ValueError("واحد طول مدل باید صریح و یکتا باشد.")
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        meshes, omitted, identities = [], [], set()
        triangle_count = 0
        for obj in model.by_type("IfcProduct"):
            if not getattr(obj, "Representation", None):
                continue
            identity = str(getattr(obj, "GlobalId", "") or "").strip()
            if not identity or identity in identities:
                raise ValueError("شناسه عنصر مدل خالی یا تکراری است.")
            identities.add(identity)
            try:
                shape = ifcopenshell.geom.create_shape(settings, obj)
            except RuntimeError:
                omitted.append(identity)
                continue
            verts = tuple(shape.geometry.verts)
            faces = tuple(shape.geometry.faces)
            if not verts or len(verts) % 3 or not faces or len(faces) % 3:
                raise ValueError("هندسه مدل فاقد شبکه مثلثی معتبر است.")
            if any(not math.isfinite(v) for v in verts):
                raise ValueError("مختصات مدل باید متناهی باشند.")
            if any(not math.isfinite(x+y+z) or not math.isfinite(x-y)
                   for x,y,z in zip(verts[::3], verts[1::3], verts[2::3])):
                raise ValueError("مختصات مدل برای نمایش بیش از حد بزرگ است.")
            if any(type(i) is not int or i < 0 or i >= len(verts) // 3 for i in faces):
                raise ValueError("ارجاع رأس در شبکه مدل نامعتبر است.")
            triangle_count += len(faces) // 3
            if triangle_count > max_triangles:
                raise ValueError("مدل از ظرفیت نمایش مثلث‌ها بزرگ‌تر است؛ مدل کوچک‌تری باز کنید.")
            meshes.append(IFCDisplayMesh(identity, str(getattr(obj, "Name", "") or ""),
                                         tuple(zip(verts[::3], verts[1::3], verts[2::3])),
                                         tuple(zip(faces[::3], faces[1::3], faces[2::3]))))
        if not meshes:
            raise ValueError("مدل فاقد هندسه قابل نمایش است.")
        return IFCDisplayDocument(str(p), hashlib.sha256(raw).hexdigest(), tuple(meshes), tuple(omitted))

    def read(self,path):
        p=Path(path)
        if not p.exists() or not p.is_file(): raise FileNotFoundError(p)
        try: import ifcopenshell
        except ImportError as exc: raise RuntimeError("Install ifcopenshell for deep BIM/IFC support") from exc
        model=ifcopenshell.open(str(p)); rows=[]
        shape_engine=None
        try:
            import ifcopenshell.geom
            settings=ifcopenshell.geom.settings()
            settings.set("use-world-coords", True)
            shape_engine=(ifcopenshell.geom.create_shape, settings)
        except Exception:
            shape_engine=None
        for obj in model.by_type("IfcProduct"):
            typ=str(obj.is_a()).upper()
            mapped=_TYPE_MAP.get(typ)
            if not mapped: continue
            props=_props(obj)
            geometry={}
            for key in ("Length","Width","Height","Depth","Area","Volume","NetVolume","GrossVolume"):
                if key in props:
                    try: geometry[key.lower()]=float(props[key])
                    except (TypeError,ValueError): pass
            if shape_engine:
                try:
                    shape=shape_engine[0](shape_engine[1], obj)
                    verts=list(shape.geometry.verts)
                    if verts:
                        xs=verts[0::3]; ys=verts[1::3]; zs=verts[2::3]
                        geometry.update({"bbox_length":max(xs)-min(xs),"bbox_width":max(ys)-min(ys),"bbox_height":max(zs)-min(zs)})
                except Exception:
                    pass
            type_name=None
            for rel in getattr(obj,"IsTypedBy",()) or ():
                type_obj=getattr(rel,"RelatingType",None)
                if type_obj: type_name=str(getattr(type_obj,"Name","") or "") or None
            rows.append(BIMElement(
                global_id=str(obj.GlobalId),ifc_type=typ,name=str(getattr(obj,"Name","") or ""),
                domain=mapped[0],kind=mapped[1],level=_level(obj),type_name=type_name,
                material_names=_materials(obj),properties=props,geometry=geometry,
                source_id=f"ifc:{p.name}:{obj.GlobalId}"))
        return tuple(rows)


@dataclass(frozen=True)
class IFCDisplayMesh:
    global_id: str
    name: str
    vertices: tuple
    triangles: tuple


@dataclass(frozen=True)
class IFCDisplayDocument:
    source: str
    source_sha256: str
    meshes: tuple[IFCDisplayMesh, ...]
    omitted_ids: tuple[str, ...]
