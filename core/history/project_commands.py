"""Undo/redo integration helpers for mutable project dictionaries."""
from __future__ import annotations
from copy import deepcopy
from .undo import CommandStack

class ProjectHistory:
    def __init__(self, project: dict, limit=100):
        if not isinstance(project,dict): raise TypeError("project must be a dict")
        self.project=project; self.stack=CommandStack(limit)
    def set_value(self, path: list[str], value):
        if not path or not all(isinstance(x,str) and x for x in path): raise ValueError("path is required")
        old=deepcopy(self.project); new=deepcopy(self.project); cur=new
        try:
            for key in path[:-1]: cur=cur[key]
            cur[path[-1]]=value
        except (KeyError,TypeError) as exc:
            raise ValueError(f"invalid project path: {path}") from exc
        def do(): self.project.clear(); self.project.update(deepcopy(new))
        def undo(): self.project.clear(); self.project.update(deepcopy(old))
        self.stack.execute(do,undo)
    def undo(self): return self.stack.undo()
    def redo(self): return self.stack.redo()
