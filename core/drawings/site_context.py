"""Verified, strictly read-only IFC4 IfcSite terrain context.

IfcSite is *spatial context*, NOT IfcElement. It must never enter element
identity ledgers, BIM QTO, member selection, or BOQ/takeoff workflows.
Only one explicitly represented site in a site-only IFC4 is supported here.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path

MAX_TRIANGLES = 40_000


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_site_context(path, *, revision: str, expected_sha256: str | None = None,
                          max_triangles: int = MAX_TRIANGLES):
    """Open original IfcSite tessellation in metres, no inferred quantities."""
    import ifcopenshell
    import ifcopenshell.geom
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("نسخهٔ منبع IFC Site باید صریح باشد.")
    if type(max_triangles) is not int or not 1 <= max_triangles <= MAX_TRIANGLES:
        raise ValueError("ظرفیت امن نمایش زمین حداکثر ۴۰ هزار مثلث است.")
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".ifc":
        raise ValueError("فایل IFC معتبر برای نمایش زمین لازم است.")
    sha = file_digest(path)
    if expected_sha256 is not None and expected_sha256 != sha:
        raise ValueError("هش منبع IFC Site تغییر کرده است.")
    model = ifcopenshell.open(str(path))
    if str(model.schema) != "IFC4" or len(model.by_type("IfcProject")) != 1:
        raise ValueError("نمای زمین فقط IFC4 با پروژهٔ یکتا را می‌پذیرد.")
    if model.by_type("IfcElement"):
        raise ValueError("نمای صرفاً مکانی برای فایل دارای IfcElement نیست؛ مسیر معمول اعضا را باز کنید.")
    sites = model.by_type("IfcSite")
    if len(sites) != 1 or not getattr(sites[0], "Representation", None):
        raise ValueError("مدل باید دقیقاً یک IfcSite دارای هندسهٔ صریح داشته باشد.")
    site = sites[0]
    identity = str(getattr(site, "GlobalId", "") or "")
    if len(identity) != 22 or ifcopenshell.guid.compress(ifcopenshell.guid.expand(identity)) != identity:
        raise ValueError("شناسهٔ مکانی IfcSite نامعتبر است.")
    units = model.by_type("IfcProject")[0].UnitsInContext
    lengths = [u for u in getattr(units, "Units", ()) if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    if len(lengths) != 1:
        raise ValueError("واحد طول منبع زمین باید یکتا باشد.")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    shape = ifcopenshell.geom.create_shape(settings, site)
    rawv = tuple(shape.geometry.verts)
    rawf = tuple(shape.geometry.faces)
    if len(rawv) < 9 or len(rawv) % 3 or not rawf or len(rawf) % 3:
        raise ValueError("شبکهٔ مثلثی IfcSite قابل نمایش نیست.")
    if len(rawf) // 3 > max_triangles:
        raise ValueError("مدل زمین از ظرفیت ۴۰ هزار مثلث فراتر است.")
    if any(not math.isfinite(v) or abs(v) > 1e12 for v in rawv):
        raise ValueError("مختصات زمین متناهی و قابل نمایش نیست.")
    vertices = tuple(tuple(rawv[i:i+3]) for i in range(0, len(rawv), 3))
    faces = tuple(tuple(rawf[i:i+3]) for i in range(0, len(rawf), 3))
    for f in faces:
        if any(type(i) is not int or i < 0 or i >= len(vertices) for i in f) or len(set(f)) != 3:
            raise ValueError("ارجاع مثلث هندسهٔ زمین نامعتبر است.")
    if file_digest(path) != sha:
        raise ValueError("منبع زمین هنگام بارگذاری تغییر کرده است.")
    return SiteTerrainScene(source_path=str(path), source_sha256=sha, revision=revision,
                            site_global_id=identity, vertices=vertices, triangles=faces)


class SiteTerrainScene:
    """Independent visualization; deliberately does NOT implement .pick or .meshes."""

    def __init__(self, *, source_path, source_sha256, revision,
                 site_global_id, vertices, triangles):
        self.source_path, self.source_sha256, self.revision = source_path, source_sha256, revision
        self.site_global_id = site_global_id
        self.vertices = vertices
        self.triangles = triangles
        self.quantity_authority = False
        self.element_global_ids = frozenset()
        self.display_kind = "IfcSite-spatial-only"
        self.center = tuple((min(v[i] for v in vertices) + max(v[i] for v in vertices))/2 for i in range(3))
        self.span = max(max(v[i] for v in vertices)-min(v[i] for v in vertices) for i in range(3))
        self.yaw, self.pitch, self.zoom = math.radians(35), math.radians(24), 1.0
        self.pan_x, self.pan_y = 0., 0.

    def validate_source(self):
        if file_digest(self.source_path) != self.source_sha256:
            raise ValueError("فایل IFC Site پس از بارگذاری تغییر کرده است.")

    def orbit(self, dy, dp):
        if any(not math.isfinite(float(x)) for x in (dy, dp)):
            raise ValueError("مختصات نمای زمین نامعتبر است.")
        self.yaw = (self.yaw + float(dy)) % (math.pi * 2)
        self.pitch = max(-math.pi/2 + 0.03, min(math.pi/2 - 0.03, self.pitch + float(dp)))

    def pan(self, dx, dy):
        if any(not math.isfinite(float(x)) for x in (dx, dy)):
            raise ValueError("حرکت نمای زمین نامعتبر است.")
        self.pan_x += float(dx)
        self.pan_y += float(dy)

    def set_zoom(self, change):
        if not math.isfinite(float(change)) or change <= 0:
            raise ValueError("بزرگ‌نمایی زمین نامعتبر است.")
        self.zoom = max(0.1, min(40.0, self.zoom * change))

    def projected_triangles(self, width, height):
        if width < 1 or height < 1:
            return ()
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        size = .8*min(width,height)/max(self.span,1e-6)*self.zoom
        points = []
        for xyz in self.vertices:
            x,y,z = (xyz[i]-self.center[i] for i in range(3))
            u, v = c*x+s*y, -s*x+c*y
            h = math.sin(self.pitch)*v - math.cos(self.pitch)*z
            d = math.cos(self.pitch)*v + math.sin(self.pitch)*z
            points.append((width/2+u*size+self.pan_x,height/2+h*size+self.pan_y,d))
        faces = [(sum(points[i][2] for i in face)/3,
                  tuple((points[i][0],points[i][1]) for i in face))
                 for face in self.triangles]
        return tuple(points for _,points in sorted(faces,key=lambda item:item[0]))
