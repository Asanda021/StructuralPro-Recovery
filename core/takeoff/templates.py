"""Reusable, explicit-input quantity-takeoff templates.

A template is an input contract, not a source of hidden quantities or rates.
Formula strings are descriptive and must be evaluated by the deterministic
calculation engine with all required values supplied by the user.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TakeoffTemplate:
    code: str
    name: str
    item_type: str
    fields: tuple[str, ...]
    formula: str
    unit: str = ""
    discipline: str = "building"


DEFAULT_TEMPLATES = (
    TakeoffTemplate("WALL-AREA", "دیوار", "wall", ("count", "length", "height", "openings"),
                    "count * (length * height - openings)", "m2"),
    TakeoffTemplate("FLOOR-AREA", "کف/سقف", "slab", ("count", "length", "width", "openings"),
                    "count * (length * width - openings)", "m2"),
    TakeoffTemplate("COLUMN-VOL", "ستون بتنی", "column", ("count", "width", "depth", "height"),
                    "count * width * depth * height", "m3"),
    TakeoffTemplate("BEAM-VOL", "تیر بتنی", "beam", ("count", "length", "width", "depth"),
                    "count * length * width * depth", "m3"),
    TakeoffTemplate("FOOT-VOL", "پی بتنی", "footing_concrete", ("count", "length", "width", "thickness"),
                    "count * length * width * thickness", "m3"),
    TakeoffTemplate("SHEAR-WALL-VOL", "دیوار برشی", "shear_wall", ("count", "length", "thickness", "height"),
                    "count * length * thickness * height", "m3"),
    TakeoffTemplate("EXCAVATION-VOL", "خاکبرداری", "excavation", ("count", "length", "width", "depth"),
                    "count * length * width * depth", "m3", "civil"),
    TakeoffTemplate("REBAR-WEIGHT", "وزن آرماتور", "rebar", ("count", "length", "unit_weight"),
                    "count * length * unit_weight", "kg"),
    TakeoffTemplate("STEEL-WEIGHT", "وزن عضو فولادی", "steel", ("count", "length", "unit_weight"),
                    "count * length * unit_weight", "kg", "advanced"),
    TakeoffTemplate("STAIR-VOL", "بتن پله", "stair_concrete", ("count", "sloped_length", "width", "waist_thickness"),
                    "count * sloped_length * width * waist_thickness", "m3"),
    TakeoffTemplate("JOIST-BLOCK", "سقف تیرچه‌بلوک", "joist_block_roof",
                    ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth"),
                    "engine:joist_block_roof", "m3"),
    TakeoffTemplate("JOIST-FOAM", "سقف تیرچه یونولیت", "joist_foam_roof",
                    ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth"),
                    "engine:joist_foam_roof", "m3"),
    TakeoffTemplate("MASONRY-BLOCK", "دیوار بلوکی", "block_wall",
                    ("length", "height", "thickness", "block_length", "block_height", "block_thickness",
                     "joint_thickness", "cement_parts", "sand_parts"),
                    "engine:block_wall", "mixed", "masonry"),
)


class TemplateLibrary:
    def __init__(self, templates=DEFAULT_TEMPLATES):
        items = {x.code: x for x in templates}
        if len(items) != len(tuple(templates)):
            raise ValueError("کد قالب متره تکراری است")
        self.items = items

    def search(self, q=""):
        q = str(q or "").casefold().strip()
        return [x for x in self.items.values() if not q or q in x.code.casefold() or q in x.name.casefold()]

    def get(self, code):
        try:
            return self.items[code]
        except KeyError as exc:
            raise KeyError(f"قالب متره ناشناخته است: {code}") from exc
