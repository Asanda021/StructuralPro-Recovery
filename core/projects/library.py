"""Project library facade."""
from __future__ import annotations
from core.projects.workflow import export_package,import_package,backup_project,project_health
class ProjectLibrary:
    def __init__(self,store): self.store=store
    def search(self,query=""):
        q=(query or "").strip().lower()
        return [p for p in self.store.list() if not q or q in str(p.get("id","")).lower() or q in str(p.get("name","")).lower()]
    def health(self,project_id): return project_health(self.store.get(project_id))
    def clone(self,source_id,target_id,target_name=None):
        """Clone into a *new* identity. Never replace an existing project.

        Production ProjectStore exposes create_only, enforced atomically inside
        SQLite. The single-argument legacy in-memory adapter is retained for
        old tests; two-argument adapters without create_only fail closed.
        """
        from inspect import signature
        from core.projects.project_model import _identity
        project=self.store.get(source_id)
        if not project: raise KeyError(source_id)
        target_key=_identity(target_id)
        if not target_key or target_key==_identity(source_id):
            raise ValueError("شناسه مقصد نامعتبر است یا با پروژه اصلی یکسان است.")
        if any(_identity(item.get("id"))==target_key for item in self.store.list()):
            raise ValueError("شناسه پروژه مقصد قبلاً وجود دارد.")
        payload={"id":target_id,"name":target_name or project.get("name","")+" (copy)",
                 "takeoffs":project.get("takeoffs",[]),"boq":project.get("boq",[]),"revisions":[]}
        params=signature(self.store.save).parameters
        if "create_only" in params:
            return self.store.save(target_id,payload,create_only=True)
        if len(params)==1:
            # Legacy in-memory fixture only, not a concurrency-safe repository.
            return self.store.save(payload)
        raise RuntimeError("Clone requires an atomic create-only project store")
    def revisions(self,project_id): return self.store.revisions(project_id)
    def export(self,project_id,path): return export_package(self.store.get(project_id),path)
    def import_package(self,path): return import_package(path)
    def backup(self,project_id,path): return backup_project(self.store.get(project_id),path)
