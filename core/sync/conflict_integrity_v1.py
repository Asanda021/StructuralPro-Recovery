"""Explicit conflict audit and fail-closed resolution boundary."""
import hashlib,json
from dataclasses import dataclass
@dataclass(frozen=True)
class ConflictEvidence:
 path:str; base:object; local:object; remote:object
 def validate(self):
  if not self.path.strip() or self.local==self.remote: raise ValueError("invalid conflict")
  return self
def collect_conflicts(merged):
 out=[]
 def walk(x,path=""):
  if isinstance(x,dict):
   if "_conflict" in x:
    c=x["_conflict"]; out.append(ConflictEvidence(path,c.get("base"),c.get("local"),c.get("remote")))
   else:
    for k in sorted(x): walk(x[k],f"{path}.{k}" if path else k)
 walk(merged); return tuple(x.validate() for x in out)
def resolve_all(merged,choices):
 conflicts={x.path:x for x in collect_conflicts(merged)}
 if set(choices)-set(conflicts): raise ValueError("unknown conflict path")
 out=json.loads(json.dumps(merged))
 for path in sorted(choices):
  choice=choices[path]
  if choice not in {"base","local","remote"}: raise ValueError("invalid conflict choice")
  cur=out
  for p in path.split(".")[:-1]: cur=cur[p]
  cur[path.split(".")[-1]]=cur[path.split(".")[-1]]["_conflict"][choice]
 if collect_conflicts(out): raise ValueError("unresolved conflicts remain")
 return out
def fingerprint(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()