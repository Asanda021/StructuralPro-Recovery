"""E2-backed IFC 3D presentation state: no new storage, no BOQ writes."""
from __future__ import annotations

from math import isfinite

from core.platform.autosave import _checked_view


def capture_state(scene, canvas):
    scene.validate_source()
    state = {
        "source_sha256": scene.source_sha256,
        "revision": scene.revision,
        "yaw": scene.yaw, "pitch": scene.pitch, "zoom": scene.zoom,
        "pan_x": scene.pan_x, "pan_y": scene.pan_y,
        "storey_id": canvas.storey_id,
        "global_id": canvas.selected_id,
        "isolate": bool(canvas.isolate_selection),
        "transparent": bool(canvas.transparent),
        "section_z": scene.section_z,
        "hidden_storeys": sorted(scene.hidden_storeys),
        "hidden_types": sorted(scene.hidden_types),
    }
    _checked_view({"ifc3d_state": state})
    return state


def verified_state(scene, state):
    """Validate *all* fields before changing a single property of the live view."""
    scene.validate_source()
    _checked_view({"ifc3d_state": state})
    if scene.source_sha256 != state["source_sha256"] or scene.revision != state["revision"]:
        raise ValueError("منبع یا Revision نمای سه‌بعدی با نشست مطابقت ندارد.")
    floor_set = set(scene.storeys)
    type_set = {m.ifc_type for m in scene.meshes}
    ids = {m.global_id for m in scene.meshes}
    if state["storey_id"] is not None and state["storey_id"] not in floor_set:
        raise ValueError("طبقه منتخب در IFC فعلی موجود نیست.")
    if state["global_id"] is not None and state["global_id"] not in ids:
        raise ValueError("عضو منتخب در IFC فعلی موجود نیست.")
    if not set(state["hidden_storeys"]).issubset(floor_set):
        raise ValueError("طبقه پنهان‌شده در IFC فعلی موجود نیست.")
    if not set(state["hidden_types"]).issubset(type_set):
        raise ValueError("رشته پنهان‌شده در IFC فعلی موجود نیست.")
    return state


def apply_state(scene, canvas, state):
    state = verified_state(scene, state)
    scene.yaw, scene.pitch, scene.zoom = state["yaw"], state["pitch"], state["zoom"]
    scene.pan_x, scene.pan_y = state["pan_x"], state["pan_y"]
    scene.set_section(state["section_z"])
    scene.hidden_storeys = set(state["hidden_storeys"])
    scene.hidden_types = set(state["hidden_types"])
    canvas.storey_id = state["storey_id"]
    canvas.selected_id = state["global_id"]
    canvas.isolate_selection = state["isolate"]
    canvas.transparent = state["transparent"]
    canvas.update()


def verified_document_id(service, project_id, scene):
    scene.validate_source()
    documents = service.project_documents(project_id)
    # Only a single registered *physical* source with matching bytes may bind
    # presentation state; duplicate attachments are ambiguous, never guessed.
    matches = [d for d in documents if d.get("integrity") == "verified"
               and d.get("sha256") == scene.source_sha256
               and d.get("path") == str(__import__('pathlib').Path(scene.source_path).resolve())]
    if len(matches) != 1:
        raise ValueError("مدرک IFC معتبر و یکتا در پرونده پروژه ثبت نشده است.")
    return matches[0]["id"]


def save_to_e2(service, project_id, scene, canvas):
    document_id = verified_document_id(service, project_id, scene)
    return service.save_view_session(project_id, {
        "document_id": document_id,
        "ifc3d_state": capture_state(scene, canvas),
    })


def restore_from_e2(service, project_id, snapshot_id, scene, canvas):
    document_id = verified_document_id(service, project_id, scene)
    view = service.restore_view_session(project_id, snapshot_id)
    if view.get("document_id") != document_id or "ifc3d_state" not in view:
        raise ValueError("نشست مربوط به همین مدرک IFC نیست.")
    state = verified_state(scene, view["ifc3d_state"])
    apply_state(scene, canvas, state)
    return state
