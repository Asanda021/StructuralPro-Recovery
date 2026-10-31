"""Evidence-gated drawing intake and editable quantity-linked construction schedule.

The suggested durations are transparent initial assumptions, NOT project
production rates, sanctioned codes, quantities, completion dates, or accepted
contractual baselines. Engineering review is required.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from itertools import chain
from decimal import Decimal, InvalidOperation
import re
import unicodedata

_STRUCTURE_MARKERS = {
    # Reinforcement, foundation concrete, IPE and steel plates may coexist
    # in either structure system. They are NOT proof of the main frame type.
    "concrete": (
        "اسکلت بتنی", "ستون بتنی", "تیر بتنی", "قاب بتنی",
        "REINFORCED CONCRETE FRAME", "CONCRETE FRAME",
        "RC COLUMN", "RC BEAM", "RC-COLUMN", "RC-BEAM",
        "CONC COLUMN", "CONC BEAM",
    ),
    "steel": (
        "اسکلت فولادی", "اسکلت فلزی", "ستون فلزی", "ستون فولادی",
        "تیر فولادی", "قاب فلزی", "قاب فولادی",
        "STEEL FRAME", "STEEL COLUMN", "STEEL BEAM",
    ),
}
_STRUCTURE_OPTIONS = frozenset(("unknown", "concrete", "steel", "mixed"))
_DISCIPLINES = frozenset(("structure", "architecture", "mechanical",
                          "electrical", "elevator", "fire", "site",
                          "wood", "renovation", "restoration"))

# Approximate WORKING DAYS only. These are placeholders to be reviewed against
# drawings, number of floors, crews, method statement, actual production and
# calendars. No fictional schedule dates, progress or verified quantities.
_WORK = (
    ("mobilize", "تجهیز کارگاه", "structure", 3, ()),
    ("earthwork", "خاک‌برداری و آماده‌سازی", "structure", 5, ("mobilize",)),
    ("foundation", "فونداسیون و شناژ", "structure", 10, ("earthwork",)),
    ("concrete_frame", "اسکلت بتن‌آرمه", "structure", 18, ("foundation",)),
    ("steel_frame", "اسکلت فولادی", "structure", 16, ("foundation",)),
    ("structure_unknown", "اسکلت؛ نوع نامشخص", "structure", 0, ("foundation",)),
    ("slabs", "سقف و دال‌ها", "structure", 12, ("FRAME",)),
    ("masonry", "دیوارچینی و تیغه‌بندی", "architecture", 10, ("slabs",)),
    ("rough_mechanical", "لوله‌کشی و تأسیسات مکانیکی توکار", "mechanical", 10, ("masonry",)),
    ("rough_electrical", "لوله‌گذاری و تأسیسات برقی توکار", "electrical", 10, ("masonry",)),
    ("plaster", "اندود و گچ‌کاری", "architecture", 8, ("ROUGH",)),
    ("facade", "نمای ساختمان", "architecture", 14, ("masonry",)),
    ("doors_windows", "درب و پنجره", "architecture", 8, ("masonry",)),
    ("finishes", "کف‌سازی، کاشی‌کاری و نازک‌کاری", "architecture", 12, ("plaster",)),
    ("mechanical_finish", "تجهیز و تست مکانیکی", "mechanical", 8, ("rough_mechanical",)),
    ("electrical_finish", "نصب و تست برق", "electrical", 8, ("rough_electrical",)),
    ("elevator", "نصب و آزمایش آسانسور", "elevator", 14, ("slabs",)),
    ("fire", "سیستم اعلام و اطفای حریق و آزمون", "fire", 8, ("slabs",)),
    ("site", "محوطه‌سازی", "site", 7, ("slabs",)),
    ("handover", "آزمایش‌ها، رفع نقص و تحویل", "structure", 5, ("ALL",)),
)
# Conservative title/layer mapping. Unrecognized takeoffs are left UNASSIGNED
# and may only be assigned manually, never counted twice from fuzzy matching.
_ITEM_MARKERS = (
    # Generic rebar/steel labels cannot establish foundation-vs-column
    # ownership; leave those rows explicitly unassigned for engineering review.
    ("rebar", "foundation", ("آرماتور فونداسیون", "میلگرد پی", "FOUNDATION REBAR")),
    ("steel", "steel_frame", ("اسکلت فولادی", "ستون فولادی", "تیرآهن", "STEEL FRAME", "STEEL COLUMN", "STEEL BEAM")),
    ("concrete", "concrete_frame", ("ستون بتنی", "اسکلت بتنی", "بتن آرمه", "CONCRETE FRAME")),
    ("wall", "masonry", ("دیوار", "بلوک", "تیغه", "MASONRY", "BLOCK WALL")),
    ("roof", "slabs", ("سقف", "دال", "SLAB")),
    ("pipe", "rough_mechanical", ("لوله آب", "فاضلاب", "کانال هوا", "DRAIN", "PLUMBING")),
    ("wire", "rough_electrical", ("کابل", "سیم کشی", "سیم‌کشی", "CONDUIT", "CABLE")),
    ("facade", "facade", ("نما", "FACADE")),
    ("floor", "finishes", ("سرامیک", "کاشی", "کف سازی", "کف‌سازی", "TILE")),
    ("plaster", "plaster", ("گچ", "اندود", "PLASTER")),
    ("window", "doors_windows", ("پنجره", "درب", "WINDOW", "DOOR")),
    ("lift", "elevator", ("آسانسور", "ELEVATOR", "LIFT")),
    ("fire", "fire", ("اطفا", "اطفاء", "اعلام حریق", "FIRE ALARM")),
)


def _normalize(value) -> str:
    return (unicodedata.normalize("NFKC", str(value or ""))
            .replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
            .upper().strip())


def _has(text: str, token: str) -> bool:
    term = _normalize(token)
    if term.isascii() and len(term) <= 4:
        # Do not confuse RC or IPE with a substring of an unrelated layer.
        return re.search(r"(?<![A-Z0-9])" + re.escape(term) + r"(?![A-Z0-9])", text) is not None
    return term in text


def infer_structure(document) -> dict:
    """Propose frame type only from explicit layer names or source CAD labels.

    Columns, LINE geometry and a concrete foundation alone do not establish
    the building's superstructure material. No quantity or BOQ is changed.
    """
    if document is None:
        return {"kind": "unknown", "confidence": "insufficient",
                "evidence": [], "reason": "نقشه دارای هندسه/متن CAD قابل بررسی نیست"}
    samples = {"concrete": [], "steel": []}
    # Read layer names and text labels only; generic shape is not an oracle.
    # Avoid duplicating 100K+ labels into a temporary list when opening
    # dense CAD drawings; classify from source identifiers in one pass.
    sources = chain(
        (("لایه", x) for x in getattr(document, "layers", ())),
        (("نوشته", x) for x in getattr(document, "text_labels", ())),
        (("بلوک", x) for x in getattr(document, "block_counts", {})),
    )
    for origin, raw in sources:
        txt = _normalize(raw)
        for kind, markers in _STRUCTURE_MARKERS.items():
            matching = next((t for t in markers if _has(txt, t)), None)
            if matching is not None and (origin, str(raw)) not in samples[kind] and len(samples[kind]) < 12:
                samples[kind].append((origin, str(raw)))
    concrete, steel = samples["concrete"], samples["steel"]
    if concrete and steel:
        kind = "mixed"
    elif concrete:
        kind = "concrete"
    elif steel:
        kind = "steel"
    else:
        kind = "unknown"
    evidence = ([{"category": k, "source": src, "label": label}
                 for k, seq in samples.items() for src, label in seq])
    return {
        "kind": kind,
        "confidence": ("insufficient" if kind == "unknown"
                       else "ambiguous" if kind == "mixed"
                       else "indicative" if len(evidence) == 1 else "corroborated"),
        "evidence": evidence,
        "reason": ("تشخیص پیشنهادی از نوشته‌ها/لایه‌های منبع، نیازمند تأیید مهندس"
                   if evidence else "مدرک صریح کافی برای تشخیص جنس اسکلت یافت نشد"),
    }


def _frame(structure):
    return ("steel_frame" if structure == "steel"
            else "concrete_frame" if structure == "concrete"
            else "structure_unknown")


def _validate_dependencies(tasks):
    ids = {x["id"] for x in tasks}
    if len(ids) != len(tasks):
        raise ValueError("Duplicate schedule activity identifier")
    graph = {}
    for task in tasks:
        deps = task["predecessors"]
        if not isinstance(deps, list) or len(deps) != len(set(deps)) or any(d not in ids or d == task["id"] for d in deps):
            raise ValueError("پیش‌نیاز فعالیت نامعتبر یا تکراری است")
        graph[task["id"]] = deps
    visiting, done = set(), set()
    def visit(key):
        if key in visiting: raise ValueError("چرخه در روابط زمان‌بندی مجاز نیست")
        if key in done: return
        visiting.add(key)
        for dep in graph[key]: visit(dep)
        visiting.remove(key)
        done.add(key)
    for key in graph: visit(key)


def recompute_schedule(plan: dict) -> dict:
    from core.projects.precedence_model import calculate_precedence
    return calculate_precedence(plan)


def new_workflow_plan(*, drawing_source: str, source_sha256: str,
                      structure: str, disciplines, inference=None,
                      project_kind: str = "new_build") -> dict:
    if project_kind not in {"new_build","renovation","fitout"}:
        raise ValueError("نوع پروژه برای زمان‌بندی معتبر نیست")
    if structure not in _STRUCTURE_OPTIONS:
        raise ValueError("نوع اسکلت انتخابی شناخته‌شده نیست")
    selected = set(disciplines)
    if selected - _DISCIPLINES:
        raise ValueError("رشته انتخابی شناخته‌شده نیست")
    selected.add("structure")
    if project_kind=="renovation":selected.add("renovation")
    # For mixed frames include both, but keep engineering ambiguity explicit.
    if structure == "mixed":
        frames = ("concrete_frame", "steel_frame")
    else:
        frames = (_frame(structure),)
    tasks = []
    for task_id, title, discipline, default_days, deps in _WORK:
        if discipline not in selected:
            continue
        # Do not invent excavation, foundation and new superstructure when
        # opening an existing building for fitout/renovation. The engineer may
        # still add specific structural works as documented measured tasks.
        if project_kind!="new_build" and task_id in {
            "earthwork","foundation","concrete_frame","steel_frame",
            "structure_unknown","slabs",
        }:
            continue
        if task_id in {"concrete_frame", "steel_frame", "structure_unknown"} and task_id not in frames:
            continue
        mapped = []
        for d in deps:
            if d == "FRAME":
                mapped.extend(frames)
            elif d == "ROUGH":
                mapped.extend(
                    task_name for task_name, scope in (
                        ("rough_mechanical", "mechanical"),
                        ("rough_electrical", "electrical"),
                    ) if scope in selected
                )
                if not mapped: mapped.append("masonry")
            elif d == "ALL":
                mapped.extend(t["id"] for t in tasks if t["id"] not in {"mobilize", "earthwork", "foundation"})
            else:
                mapped.append(d)
        # If selected scopes omit a predecessor, use the nearest existing
        # ancestor, not a fictitious task or an invalid reference.
        present = {t["id"] for t in tasks}
        mapped = [p for p in dict.fromkeys(mapped) if p in present]
        if not mapped and tasks and task_id not in {"mobilize", "earthwork", "foundation"}:
            mapped = [frames[-1]] if frames[-1] in present else ["foundation"]
        tasks.append({
            "id": task_id, "title": title, "discipline": discipline,
            "duration_days": default_days,"default_duration_days":default_days,
            "base_predecessors":list(mapped),
            "duration_status":"OFFICE_INITIAL_ASSUMPTION",
            "duration_edited": False,"predecessors_edited":False,
            "crew": "تعیین نشده", "predecessors": mapped,
            "linked_item_ids": [], "measured": {}, "quantity_reviewed": False,
            "baseline_approved": False,
        })
    # Optional detailed WBS profiles are zero-duration until a verified,
    # unit-compatible quantity exists. Their first rates are only planning
    # heuristics; none may silently add quantities or financial BOQ rows.
    from core.projects.production_catalog import CATALOG
    planned = {task["id"] for task in tasks}
    for profile in CATALOG.values():
        if profile.discipline not in selected:
            continue
        if project_kind!="new_build" and profile.discipline=="structure":
            continue
        # The frame type is a reviewer choice; don't create fabrication for
        # steel under a confirmed concrete-only structure.
        if profile.code.startswith("steel_") and structure=="concrete":
            continue
        if profile.code.startswith(("column_","slab_","beam_")) and structure=="steel":
            continue
        pred = profile.predecessor if profile.predecessor in planned else (
            "foundation" if profile.discipline in {"structure", "wood"} else
            "masonry" if "masonry" in planned else "slabs" if "slabs" in planned else "mobilize"
        )
        t={
            "id":profile.code,"title":profile.title,"discipline":profile.discipline,
            "duration_days":0,"duration_edited":False,
            "duration_status":"AWAITING_REVIEWED_QUANTITY",
            "crew":f"{profile.crews} اکیپ پیشنهادی",
            "crew_count":profile.crews,"efficiency":"1",
            "rate_source":profile.rate_source,
            "rate_unit":profile.unit,
            "rate_low_per_crew_day":profile.low_per_crew_day,
            "rate_high_per_crew_day":profile.high_per_crew_day,
            "predecessors":[pred],"links":[{
                "predecessor":pred,"type":profile.relation,
                "lag_days":profile.lag_days,
            }],
            "linked_item_ids":[],"measured":{},"quantity_reviewed":False,
            "baseline_approved":False,
        }
        tasks.append(t)
        planned.add(profile.code)
    # Final handover cannot predate selected detailed activities. Zero-duration
    # unmeasured placeholders add no artificial days and remain transparent.
    handover=next((task for task in tasks if task["id"]=="handover"),None)
    if handover is not None:
        handover["predecessors"]+= [
            item["id"] for item in tasks
            if item["id"] in CATALOG and item["id"] not in handover["predecessors"]
        ]
    result = {
        "schema": "structuralpro.drawing-workflow-v1",
        "status": "DRAFT_UNAPPROVED",
        "drawing_source": str(drawing_source),
        "source_sha256": str(source_sha256),
        "structure": structure,
        "project_kind":project_kind,
        "structure_inference": deepcopy(inference) if inference else {},
        "disciplines": sorted(selected),
        "calendar": {"working_days_per_week": 6, "start_date": None},
        "assumption_note": "مدت‌ها و ترتیب فعالیت‌ها فرض اولیه قابل ویرایش‌اند؛ با متره، اکیپ، روش اجرا و تقویم واقعی تطبیق و تأیید شوند",
        "tasks": tasks, "unassigned_item_ids": [],
    }
    return recompute_schedule(result)


def assign_takeoff(item, valid_task_ids) -> str | None:
    raw_label = " ".join([
        str(getattr(item, "label", "")),
        str(getattr(item, "takeoff_code", "")),
        str((getattr(item, "cad_evidence", None) or {}).get("layer", "")),
    ])
    text = _normalize(raw_label)
    matches = {task_id for _, task_id, tokens in _ITEM_MARKERS
               if task_id in valid_task_ids and any(_has(text, t) for t in tokens)}
    # Ambiguity stays unassigned rather than silently choosing a discipline.
    return next(iter(matches)) if len(matches) == 1 else None


def sync_measured_items(plan: dict, items) -> dict:
    """Update only actual measurement links, preserving edited schedule fields."""
    if plan is None: return None
    valid = {task["id"] for task in plan["tasks"]}
    linked = {task["id"]: {} for task in plan["tasks"]}
    unassigned = []
    from core.projects.production_catalog import matching_profile, productivity_days, CATALOG, normalized_production_unit
    from decimal import Decimal
    for item in items:
        ident = str(item.id)
        label = " ".join((str(getattr(item,"label","")),
                          str(getattr(item,"takeoff_code","")),
                          str((getattr(item,"cad_evidence",None) or {}).get("layer",""))))
        key = matching_profile(label,set(plan.get("disciplines",[])))
        # A label alone does not prove compatible units. Fall back to the
        # review-only summary WBS mapping without inventing numeric quantities.
        if key is not None and normalized_production_unit(item.unit)!=CATALOG[key].unit:
            key=None
        if key not in valid:
            key=None
        if key is None:
            key=assign_takeoff(item,valid)
        if key is None:
            unassigned.append(ident)
            continue
        linked[key][ident] = {
            "quantity": str(item.quantity), "unit": str(item.unit),
            "source_ref": str(item.source_ref),
            "geometry_reviewed": bool(
                getattr(item, "cad_evidence", None)
                and (item.cad_evidence.get("review") or {}).get("digest")),
        }
    for task in plan["tasks"]:
        observed = linked[task["id"]]
        task["linked_item_ids"] = sorted(observed)
        task["measured"] = observed
        task["quantity_reviewed"] = bool(observed) and all(x["geometry_reviewed"] for x in observed.values())
        if task["id"] in CATALOG and not task.get("duration_edited"):
            profile=CATALOG[task["id"]]
            if observed and all(normalized_production_unit(entry["unit"])==profile.unit for entry in observed.values()):
                total=sum((Decimal(entry["quantity"]) for entry in observed.values()), Decimal(0))
                rec=productivity_days(task["id"],total,profile.unit,
                                      crews=task.get("crew_count",profile.crews),
                                      efficiency=task.get("efficiency","1"))
                task["duration_days"]=rec["expected_workdays"]
                task["duration_range"]=[rec["min_workdays"],rec["max_workdays"]]
                task["duration_status"]="ESTIMATED_REQUIRES_SITE_REVIEW"
                task["rate_source"]=rec["source"]
            else:
                task["duration_days"]=0
                task["duration_range"]=None
                task["duration_status"]="AWAITING_REVIEWED_QUANTITY"
    # Avoid double-counting a broad WBS duration with the exact same work
    # represented as measured and detailed child activities. The summary
    # remains in the network with zero duration, waiting on real child work.
    # Never override a manually edited summary or one with its own takeoffs.
    parents={
        "block_wall":"masonry","brick_wall":"masonry","aac_wall":"masonry",
        "foundation_form":"foundation","foundation_rebar":"foundation",
        "foundation_concrete":"foundation",
        "column_rebar":"concrete_frame","column_form":"concrete_frame",
        "column_concrete":"concrete_frame",
        "beam_rebar":"slabs","slab_form":"slabs",
        "slab_rebar":"slabs","slab_concrete":"slabs",
        "steel_fabrication":"steel_frame","steel_erection":"steel_frame",
        "steel_welding":"steel_frame","steel_bolting":"steel_frame",
        "composite_deck":"slabs",
        "plaster_base":"plaster","finish_plaster":"plaster",
        "floor_screed":"finishes","waterproofing":"finishes",
        "floor_tile":"finishes","wall_tile":"finishes","stone_floor":"finishes",
        "stone_facade":"facade","brick_facade":"facade",
        "door_install":"doors_windows","aluminum_window":"doors_windows",
        "upvc_window":"doors_windows",
        "plumbing_water":"rough_mechanical","sewage_pipe":"rough_mechanical",
        "gas_pipe":"rough_mechanical","hvac_duct":"rough_mechanical",
        "hvac_pipe":"rough_mechanical",
        "conduit":"rough_electrical","wiring":"rough_electrical",
        "cable_tray":"rough_electrical","data_network":"rough_electrical",
        "radiator":"mechanical_finish","boiler":"mechanical_finish",
        "hvac_unit":"mechanical_finish","sanitary":"mechanical_finish",
        "switch_socket":"electrical_finish","panel_board":"electrical_finish",
        "lighting":"electrical_finish",
        "elevator_rail":"elevator","elevator_door":"elevator",
        "elevator_cabin":"elevator",
        "fire_alarm":"fire","fire_pipe":"fire","fire_cabinet":"fire",
        "site_paving":"site","site_kerb":"site","landscape":"site",
    }
    from collections import defaultdict
    groups=defaultdict(list)
    for child in plan["tasks"]:
        parent=parents.get(child["id"])
        if parent and child.get("linked_item_ids") and parent in valid:
            groups[parent].append(child["id"])
    for parent in plan["tasks"]:
        if parent["id"] not in groups and parent.get("duration_status")!="SUMMARY_FROM_DETAILED_WBS":
            continue
        if (parent.get("duration_edited") or parent.get("predecessors_edited")
                or parent.get("linked_item_ids")):
            continue
        children=groups.get(parent["id"],[])
        parent["duration_days"]=0 if children else parent.get("default_duration_days",0)
        parent["duration_status"]=(
            "SUMMARY_FROM_DETAILED_WBS" if children else "OFFICE_INITIAL_ASSUMPTION"
        )
        parent["predecessors"]=list(dict.fromkeys(
            parent.get("base_predecessors",parent["predecessors"])+children
        ))
        # Existing manual relationship links must not be secretly repointed;
        # unedited automatically generated summary links use basic FS.
        parent["links"]=[]
    plan["unassigned_item_ids"] = sorted(unassigned)
    return recompute_schedule(plan)


def edit_activity(plan: dict, task_id: str, *, title=None, duration_days=None,
                  crew=None, predecessors=None, crew_count=None,
                  efficiency=None, links=None) -> dict:
    draft = deepcopy(plan)
    if draft.get("status") != "DRAFT_UNAPPROVED":
        raise ValueError("ویرایش تنها برای پیش‌نویس برنامه مجاز است")
    task = next((t for t in draft["tasks"] if t["id"] == task_id), None)
    if task is None: raise ValueError("فعالیت موردنظر وجود ندارد")
    if duration_days is not None:
        if type(duration_days) is not int or not 0 <= duration_days <= 3650:
            raise ValueError("مدت باید عدد صحیح روز کاری بین صفر تا ۳۶۵۰ باشد")
        task["duration_days"] = duration_days
        task["duration_edited"] = True
    if title is not None:
        if not isinstance(title, str) or not title.strip() or len(title) > 150:
            raise ValueError("عنوان فعالیت معتبر لازم است")
        task["title"] = title.strip()
    if crew is not None:
        if not isinstance(crew, str) or not crew.strip() or len(crew) > 100:
            raise ValueError("نام اکیپ معتبر لازم است")
        task["crew"] = crew.strip()
    if crew_count is not None:
        if type(crew_count) is not int or not 1 <= crew_count <= 100:
            raise ValueError("تعداد اکیپ باید صحیح و بین ۱ تا ۱۰۰ باشد")
        task["crew_count"] = crew_count
    if efficiency is not None:
        from decimal import Decimal,InvalidOperation
        try: eff=Decimal(str(efficiency))
        except (InvalidOperation,ValueError):raise ValueError("ضریب بهره‌وری معتبر نیست")
        if not eff.is_finite() or not Decimal("0.1")<=eff<=Decimal("2"):
            raise ValueError("ضریب بهره‌وری باید بین ۰٫۱ تا ۲ باشد")
        task["efficiency"]=str(eff)
    if predecessors is not None:
        if not isinstance(predecessors, list):
            raise ValueError("پیش‌نیاز باید فهرست شناسه فعالیت باشد")
        task["predecessors"] = predecessors
        task["predecessors_edited"]=True
        # Replacing predecessor IDs must not retain obsolete relationship
        # references. The user can supply new FS/SS/FF/SF links in same edit.
        if links is None:task["links"]=[]
    if links is not None:
        if not isinstance(links,list):
            raise ValueError("روابط تقدم و تأخر باید یک فهرست باشد")
        task["links"]=links
    recompute_schedule(draft)
    return draft
