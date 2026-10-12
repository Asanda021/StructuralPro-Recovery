"""Atomic, collision-safe project backup helpers."""
from __future__ import annotations
import hashlib, json, time, zipfile
from pathlib import Path
from .integrity import validate_project

BACKUP_FORMAT="StructuralProBackup"
BACKUP_VERSION=1

class BackupManager:
    def __init__(self, root: str|Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def create(self, project: dict, project_id: str):
        if not isinstance(project,dict): raise TypeError("project must be a dict")
        stamp=time.strftime("%Y%m%d_%H%M%S")
        path=self.root/f"{project_id}_{stamp}.json"
        suffix=1
        while path.exists():
            path=self.root/f"{project_id}_{stamp}_{suffix}.json"
            suffix += 1
        tmp=path.with_name(path.name+".tmp")
        tmp.write_text(json.dumps(project,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
        tmp.replace(path)
        return path
    def list(self, project_id: str):
        return sorted(self.root.glob(f"{project_id}_*.json"), reverse=True)
    def restore(self, path: str|Path):
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("backup must contain an object")
        return data
    def create_package(self, project: dict, project_id: str):
        validation=validate_project(project)
        if not validation["valid"]: raise ValueError("cannot backup invalid project")
        stamp=time.strftime("%Y%m%d_%H%M%S")
        path=self.root/f"{project_id}_{stamp}.spbackup"
        suffix=1
        while path.exists():
            path=self.root/f"{project_id}_{stamp}_{suffix}.spbackup"
            suffix += 1
        payload=json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        manifest={"format":BACKUP_FORMAT,"version":BACKUP_VERSION,"project_id":project_id,
                  "sha256":hashlib.sha256(payload).hexdigest()}
        tmp=path.with_name(path.name+".tmp")
        with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json",payload)
            z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,sort_keys=True))
        tmp.replace(path)
        return path
    def restore_package(self, path: str|Path):
        try:
            with zipfile.ZipFile(path) as z:
                manifest=json.loads(z.read("manifest.json").decode())
                payload=z.read("project.json")
        except (OSError,zipfile.BadZipFile,KeyError,json.JSONDecodeError,UnicodeDecodeError) as exc:
            raise ValueError("invalid backup package") from exc
        if manifest.get("format")!=BACKUP_FORMAT or manifest.get("version")!=BACKUP_VERSION:
            raise ValueError("unsupported backup format")
        if hashlib.sha256(payload).hexdigest()!=manifest.get("sha256"):
            raise ValueError("backup checksum mismatch")
        project=json.loads(payload.decode())
        if not validate_project(project)["valid"]: raise ValueError("backup integrity validation failed")
        if str(project.get("id","")) != str(manifest.get("project_id","")):
            raise ValueError("backup project identifier mismatch")
        return project
    def prune(self, project_id: str, keep=10):
        keep=max(1,int(keep)); files=self.list(project_id)
        for p in files[keep:]: p.unlink(missing_ok=True)
        return files[:keep]
