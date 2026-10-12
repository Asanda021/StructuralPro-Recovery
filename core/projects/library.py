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
        project=self.store.get(source_id)
        if not project: raise KeyError(source_id)
        payload={"id":target_id,"name":target_name or project.get("name","")+" (copy)",
                 "takeoffs":project.get("takeoffs",[]),"boq":project.get("boq",[]),"revisions":[]}
        try: return self.store.save(target_id,payload)
        except TypeError: return self.store.save(payload)
    def revisions(self,project_id): return self.store.revisions(project_id)
    def export(self,project_id,path): return export_package(self.store.get(project_id),path)
    def import_package(self,path): return import_package(path)
    def backup(self,project_id,path): return backup_project(self.store.get(project_id),path)
