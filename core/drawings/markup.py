"""Persistent markup primitives for drawing review."""
from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class Markup:
    id:str; kind:str; text:str=""; x:float=0; y:float=0; x2:float=0; y2:float=0; page:int|None=None
    def to_dict(self): return asdict(self)
class MarkupStore:
    def __init__(self): self.items=[]
    def add(self,markup): self.items.append(markup); return markup
    def remove(self,markup_id): self.items=[x for x in self.items if x.id!=markup_id]
    def for_page(self,page): return [x for x in self.items if x.page==page]
