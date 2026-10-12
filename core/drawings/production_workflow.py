"""Human-editable drawing production workflow with explicit review/freeze states."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import copy, hashlib, json

STATES=("imported","classified","editable","reviewed","frozen")

@dataclass
class DrawingEdit:
    source_id:str
    object_id:str
    before:dict
    after:dict
    editor:str
    note:str=""
    approved:bool=False

class ProductionDrawing:
    def __init__(self, objects=(), source_id=""):
        self.source_id=str(source_id)
        self.objects={str(x["object_id"]):copy.deepcopy(x) for x in objects}
        self.state="imported"
        self.history=[]
    def classify(self, classifier):
        if self.state not in {"imported","classified"}: raise RuntimeError("classification is closed")
        for obj in self.objects.values(): obj["classification"]=classifier(obj)
        self.state="classified"; return self.snapshot()
    def enable_editing(self):
        if self.state not in {"classified","editable"}: raise RuntimeError("drawing is not editable yet")
        self.state="editable"; return self.snapshot()
    def edit(self,object_id,changes,editor,note=""):
        if self.state!="editable": raise RuntimeError("drawing is not editable")
        key=str(object_id)
        if key not in self.objects: raise KeyError(key)
        before=copy.deepcopy(self.objects[key]); self.objects[key].update(copy.deepcopy(changes))
        self.history.append(DrawingEdit(self.source_id,key,before,copy.deepcopy(self.objects[key]),str(editor),str(note)))
        return copy.deepcopy(self.objects[key])
    def review(self, decisions):
        if self.state!="editable": raise RuntimeError("drawing must be editable before review")
        pending=[]
        for edit in self.history:
            ok=bool(decisions.get(edit.object_id,False))
            edit.approved=ok
            if not ok: pending.append(edit.object_id)
        if pending: raise ValueError(f"unapproved drawing edits: {sorted(set(pending))}")
        self.state="reviewed"; return self.snapshot()
    def freeze(self):
        if self.state!="reviewed": raise RuntimeError("drawing must be reviewed before freeze")
        self.state="frozen"; return self.snapshot()
    def snapshot(self):
        return {"source_id":self.source_id,"state":self.state,"objects":copy.deepcopy(self.objects),
                "history":[asdict(x) for x in self.history]}
    def digest(self):
        raw=json.dumps(self.snapshot(),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        return hashlib.sha256(raw).hexdigest()
