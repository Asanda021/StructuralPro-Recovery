"""Drawing sheet registry for multi-sheet navigation and revision links."""
from dataclasses import dataclass
@dataclass(frozen=True)
class DrawingSheet:
    id:str; name:str; page:int|None=None; layer:str|None=None; revision:str=""; scale:str=""
class SheetRegistry:
    def __init__(self): self.items=[]
    def add(self,**kwargs): x=DrawingSheet(**kwargs); self.items.append(x); return x
    def search(self,q=""): q=q.casefold(); return [x for x in self.items if not q or q in x.name.casefold() or q in x.id.casefold()]
