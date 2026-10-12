"""AI takeoff boundary: suggestions are never silently accepted."""
from dataclasses import dataclass

@dataclass(frozen=True)
class AISuggestion:
    source:str; description:str; quantity:float; unit:str; confidence:float
    def review_required(self)->bool: return True

def gate(suggestions):
    out=[]
    for s in suggestions:
        if not 0.0 <= float(s.confidence) <= 1.0: raise ValueError("confidence must be 0..1")
        out.append({"source":s.source,"description":s.description,"quantity":s.quantity,"unit":s.unit,"confidence":s.confidence,"needs_confirmation":True})
    return out
