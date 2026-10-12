"""Deterministic AI QA gate; LLM output never becomes engineering truth."""
from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class QAFinding:
 severity:str; code:str; message:str; source_id:str=""
 def validate(self):
  if self.severity not in {"info","warning","error"} or not self.code.strip() or not self.message.strip(): raise ValueError("invalid QA finding")
  return self
class AIQAGate:
 def __init__(self,deterministic_checker): self.checker=deterministic_checker
 def review(self,project,*,ai_notes=()):
  findings=tuple(QAFinding(**x).validate() for x in self.checker(project))
  return {"accepted":not any(x.severity=="error" for x in findings),"findings":findings,"ai_notes":tuple(str(x) for x in ai_notes if str(x).strip()),"ai_notes_are_non_authoritative":True}
 @staticmethod
 def fingerprint(result): return hashlib.sha256(json.dumps({"accepted":result["accepted"],"findings":[x.__dict__ for x in result["findings"]],"ai_notes":result["ai_notes"]},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()