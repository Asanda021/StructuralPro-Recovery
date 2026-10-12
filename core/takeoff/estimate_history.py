"""Deterministic estimate snapshots and change deltas."""
from __future__ import annotations
from copy import deepcopy

def snapshot(estimate): return deepcopy(estimate)

def delta(previous,current):
    def key(x): return str(x.get("code") or x.get("description") or x.get("item") or "")
    a={key(x):x for x in previous or []}; b={key(x):x for x in current or []}
    added=[b[k] for k in b.keys()-a.keys()]; removed=[a[k] for k in a.keys()-b.keys()]; changed=[]
    for k in a.keys() & b.keys():
        if a[k]!=b[k]: changed.append({"key":k,"previous":a[k],"current":b[k]})
    return {"added":added,"removed":removed,"changed":changed,"unchanged":len(a.keys() & b.keys())-len(changed)}
