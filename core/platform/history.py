"""Deterministic bounded undo/redo history for project state."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping

class History:
    def __init__(self, initial: Mapping[str, Any], *, limit: int = 100):
        if not isinstance(initial, Mapping): raise TypeError("initial must be a mapping")
        if not isinstance(limit,int) or limit < 1: raise ValueError("limit must be positive")
        self._limit=limit
        self._past=[deepcopy(dict(initial))]
        self._future=[]

    @property
    def can_undo(self): return len(self._past)>1
    @property
    def can_redo(self): return bool(self._future)

    def current(self) -> dict[str,Any]:
        return deepcopy(self._past[-1])

    def apply(self, state: Mapping[str,Any]) -> dict[str,Any]:
        if not isinstance(state, Mapping): raise TypeError("state must be a mapping")
        self._past.append(deepcopy(dict(state)))
        self._future.clear()
        if len(self._past)>self._limit: self._past=self._past[-self._limit:]
        return self.current()

    def undo(self) -> dict[str,Any]:
        if not self.can_undo: raise IndexError("nothing to undo")
        self._future.append(self._past.pop())
        return self.current()

    def redo(self) -> dict[str,Any]:
        if not self.can_redo: raise IndexError("nothing to redo")
        self._past.append(self._future.pop())
        return self.current()

    def clear_redo(self) -> None:
        self._future.clear()
