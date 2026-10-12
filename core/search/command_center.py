"""Command/search center for project-wide natural-language-like queries."""
from __future__ import annotations
from .global_search import search_project

COMMANDS = {
    "پروژه": "project", "متره": "takeoff", "آیتم": "item", "ردیف": "price_code",
    "فهرست": "price_code", "boq": "boq", "برآورد": "boq",
}

def command_search(project, query: str):
    q=str(query or "").strip()
    if not q: return []
    hits=search_project(project,q)
    if hits: return hits
    # fallback token intersection: useful for phrases such as "دیوار طبقه دوم"
    tokens=[t.casefold() for t in q.split() if len(t)>1]
    if len(tokens)>1:
        merged=[]
        for token in tokens:
            for h in search_project(project,token):
                key=(h["kind"],h["text"],str(h["data"]))
                if key not in {(x["kind"],x["text"],str(x["data"])) for x in merged}: merged.append(h)
        return merged
    return []
