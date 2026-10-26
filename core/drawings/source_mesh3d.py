"""Read-only 3D scene projection from the verified IFC display contract.

No guessed geometry, dimensions, floor count, quantity or member identities.
This is a 3D viewing projection ONLY, not quantity/takeoff authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

_LIMIT_TRIANGLES = 40_000


def _sha256_source(path):
    """Read source evidence in bounded chunks even for giant IFC files."""
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("مختصات سه‌بعدی باید عدد واقعی باشند.")
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1e12:
        raise ValueError("مختصات سه‌بعدی باید متناهی و قابل نمایش باشند.")
    return number


@dataclass(frozen=True)
class SourceMesh3D:
    global_id: str
    ifc_type: str
    storey_id: str | None
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class ProjectedFace:
    global_id: str
    ifc_type: str
    storey_id: str | None
    points: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    depth: float


class VerifiedScene3D:
    """Projected IFC meshes with a live orbit camera and explicit provenance."""

    def __init__(self, contract: dict, *, max_triangles=_LIMIT_TRIANGLES):
        if not isinstance(contract, dict) or contract.get("policy") != "ifc_display_geometry_v1":
            raise ValueError("قرارداد هندسه مستند IFC معتبر نیست.")
        if contract.get("quantity_authority") is not False:
            raise ValueError("نمایش سه‌بعدی نباید مجوز متره ایجاد کند.")
        if contract.get("coordinate_system") != "IFC world coordinates in metres":
            raise ValueError("دستگاه مختصات معتبر مدل مشخص نیست.")
        sha = contract.get("source_sha256")
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("هش SHA-256 منبع نامعتبر است.")
        revision = contract.get("revision")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("نسخه مستند IFC باید مشخص باشد.")
        source_path = contract.get("source_path")
        if not isinstance(source_path, str) or not Path(source_path).is_file():
            raise ValueError("فایل واقعی مدل در دسترس نیست.")
        if _sha256_source(source_path) != sha:
            raise ValueError("منبع IFC تغییر کرده و نمایش متوقف شد.")
        if isinstance(max_triangles, bool) or not isinstance(max_triangles, int) or max_triangles < 1:
            raise ValueError("حد نمایش مثلث‌ها نامعتبر است.")
        elements = contract.get("elements")
        if not isinstance(elements, list) or not elements:
            raise ValueError("مدل، عضو دارای هندسه مستند ندارد.")
        meshes, identities, total = [], set(), 0
        for element in elements:
            if not isinstance(element, dict):
                raise ValueError("رکورد عضو IFC نامعتبر است.")
            identity = element.get("global_id")
            if not isinstance(identity, str) or not identity.strip() or identity in identities:
                raise ValueError("شناسه عضو سه‌بعدی خالی یا تکراری است.")
            identities.add(identity)
            vertices = element.get("vertices_m")
            faces = element.get("triangles")
            if not isinstance(vertices, list) or not vertices or not isinstance(faces, list) or not faces:
                raise ValueError("هندسه عضو IFC ناقص است.")
            new_vertices = []
            for triple in vertices:
                if not isinstance(triple, (list, tuple)) or len(triple) != 3:
                    raise ValueError("مختصات رأس مدل سه‌بعدی ناقص است.")
                new_vertices.append(tuple(_finite_number(n) for n in triple))
            new_faces = []
            for triangle in faces:
                if (not isinstance(triangle, (list, tuple)) or len(triangle) != 3 or
                    any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or
                        i >= len(new_vertices) for i in triangle) or len(set(triangle)) != 3):
                    raise ValueError("مثلث مدل سه‌بعدی ارجاع معتبر ندارد.")
                a, b, c = (new_vertices[i] for i in triangle)
                u = tuple(b[i]-a[i] for i in range(3))
                v = tuple(c[i]-a[i] for i in range(3))
                cross = (u[1]*v[2]-u[2]*v[1],
                         u[2]*v[0]-u[0]*v[2],
                         u[0]*v[1]-u[1]*v[0])
                if sum(t*t for t in cross) <= 1e-20:
                    raise ValueError("مثلث مدل سه‌بعدی دارای هندسه صفر یا هم‌خط است.")
                new_faces.append(tuple(triangle))
            total += len(new_faces)
            if total > max_triangles:
                raise ValueError("مدل از ظرفیت تعیین‌شده نمایش سه‌بعدی بزرگ‌تر است.")
            floor = element.get("storey_id")
            if floor is not None and not isinstance(floor, str):
                raise ValueError("هویت طبقه IFC نامعتبر است.")
            ifc_type = element.get("ifc_type")
            if not isinstance(ifc_type, str) or not ifc_type:
                raise ValueError("رشته یا نوع عضو IFC مشخص نیست.")
            meshes.append(SourceMesh3D(identity, ifc_type, floor,
                                       tuple(new_vertices), tuple(new_faces)))
        self.meshes = tuple(meshes)
        self.revision = revision
        self.source_sha256 = sha
        self.source_path = source_path
        self.quantity_authority = False
        self.omitted_ids = tuple(contract.get("omitted_ids", ()))
        self.storeys = tuple(sorted({m.storey_id for m in meshes if m.storey_id is not None}))
        coords = [v for mesh in meshes for v in mesh.vertices]
        self.center = tuple((min(v[i] for v in coords) + max(v[i] for v in coords))/2
                            for i in range(3))
        self.span = max(max(v[i] for v in coords)-min(v[i] for v in coords)
                        for i in range(3))
        if not math.isfinite(self.span):
            raise ValueError("ابعاد مدل معتبر نیست.")
        self.yaw = math.radians(35)
        self.pitch = math.radians(24)
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.focus_storey_id = None
        self.focus_center = self.center
        self.focus_span = self.span
        self.hidden_storeys = set()
        self.hidden_types = set()
        self.section_z = None

    def set_section(self, z=None):
        self.section_z = None if z is None else _finite_number(z)

    def _clip_triangle(self, vertices):
        if self.section_z is None:
            return [vertices]
        polygon = []
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            inside_a, inside_b = a[2] <= self.section_z, b[2] <= self.section_z
            if inside_a:
                polygon.append(a)
            if inside_a != inside_b:
                t = (self.section_z-a[2])/(b[2]-a[2])
                polygon.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
        return [(polygon[0], polygon[i], polygon[i+1])
                for i in range(1, len(polygon)-1)]

    def orbit(self, delta_yaw: float, delta_pitch: float):
        dy, dp = _finite_number(delta_yaw), _finite_number(delta_pitch)
        self.yaw = (self.yaw + dy) % (2*math.pi)
        self.pitch = max(-math.pi/2 + 0.03, min(math.pi/2 - 0.03, self.pitch + dp))

    def pan(self, dx: float, dy: float):
        self.pan_x += _finite_number(dx)
        self.pan_y += _finite_number(dy)

    def set_zoom(self, multiplier: float):
        change = _finite_number(multiplier)
        if change <= 0:
            raise ValueError("ضریب بزرگ‌نمایی باید مثبت باشد.")
        self.zoom = max(0.1, min(40.0, self.zoom*change))

    def fit_storey(self, storey_id=None):
        """Fit documented vertices only; choosing a floor never moves geometry."""
        if storey_id is not None and storey_id not in self.storeys:
            raise ValueError("طبقه انتخابی در IFC موجود نیست.")
        if storey_id is None:
            target_center, target_span = self.center, self.span
        else:
            vertices = [v for mesh in self.meshes if mesh.storey_id == storey_id
                        for v in mesh.vertices]
            if not vertices:
                raise ValueError("طبقه انتخابی فاقد هندسه معتبر است.")
            target_center = tuple((min(p[i] for p in vertices) + max(p[i] for p in vertices)) / 2
                                  for i in range(3))
            target_span = max(max(p[i] for p in vertices) - min(p[i] for p in vertices)
                              for i in range(3))
        self.focus_storey_id = storey_id
        self.focus_center = target_center
        self.focus_span = max(target_span, 1e-6)
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0

    def reset_view(self):
        self.yaw = math.radians(35)
        self.pitch = math.radians(24)
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0

    def _project(self, xyz, width: int, height: int):
        x, y, z = (xyz[i]-self.focus_center[i] for i in range(3))
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        u, v = c*x+s*y, -s*x+c*y
        h = math.sin(self.pitch)*v - math.cos(self.pitch)*z
        depth = math.cos(self.pitch)*v + math.sin(self.pitch)*z
        scale = 0.79*min(width, height)/max(self.focus_span, 1e-6)*self.zoom
        return ((width/2+u*scale+self.pan_x, height/2+h*scale+self.pan_y), depth)

    def validate_source(self):
        try:
            actual = _sha256_source(self.source_path)
        except OSError as exc:
            raise ValueError('فایل منبع تغییر کرده یا دیگر در دسترس نیست.') from exc
        if actual != self.source_sha256:
            raise ValueError('منبع IFC تغییر کرده و نمایش متوقف شد.')

    def visible_faces(self, width: int, height: int, *,
                      storey_id: str | None = None, selected_id: str | None = None):
        if width < 1 or height < 1:
            raise ValueError("پنجره سه‌بعدی باید اندازه مثبت داشته باشد.")
        if storey_id is not None and storey_id not in self.storeys:
            raise ValueError("طبقه انتخابی در هندسه مستند وجود ندارد.")
        if selected_id is not None and selected_id not in {m.global_id for m in self.meshes}:
            raise ValueError("عضو انتخابی در مدل واقعی وجود ندارد.")
        output = []
        for mesh in self.meshes:
            if mesh.storey_id in self.hidden_storeys or mesh.ifc_type in self.hidden_types:
                continue
            if storey_id is not None and mesh.storey_id != storey_id:
                continue
            if selected_id is not None and mesh.global_id != selected_id:
                continue
            for indexes in mesh.faces:
                vertices = tuple(mesh.vertices[i] for i in indexes)
                for triangle in self._clip_triangle(vertices):
                    transformed = [self._project(p, width, height) for p in triangle]
                    output.append(ProjectedFace(mesh.global_id, mesh.ifc_type, mesh.storey_id,
                           tuple(p[0] for p in transformed),
                           sum(p[1] for p in transformed)/3))
        return tuple(sorted(output, key=lambda face: face.depth))

    @staticmethod
    def _inside(x: float, y: float, points) -> bool:
        a, b, c = points
        def cross(p,q):
            return (p[0]-x)*(q[1]-y)-(p[1]-y)*(q[0]-x)
        if abs((b[0]-a[0])*(c[1]-a[1]) -
               (b[1]-a[1])*(c[0]-a[0])) <= 1e-9:
            return False  # Edge-on/degenerate 2D projection is not selectable.
        one, two, three = cross(a,b), cross(b,c), cross(c,a)
        return not ((one < 0 or two < 0 or three < 0) and
                    (one > 0 or two > 0 or three > 0))

    def pick(self, x: float, y: float, width: int, height: int, *, storey_id=None,
             selected_id=None):
        px, py = _finite_number(x), _finite_number(y)
        for face in reversed(self.visible_faces(width,height,storey_id=storey_id,
                                               selected_id=selected_id)):
            if self._inside(px,py,face.points):
                return face.global_id
        return None
