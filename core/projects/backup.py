"""Atomic, collision-safe project backup helpers."""
from __future__ import annotations
import hashlib, json, os, shutil, time, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Mapping
from .integrity import validate_project

BACKUP_FORMAT="StructuralProBackup"
BACKUP_VERSION=2
LEGACY_BACKUP_VERSION=1
BACKUP_PRODUCER="StructuralPro"

def _publish_no_replace(temporary: Path, destination: Path) -> None:
    try:
        os.link(temporary,destination)
    except FileExistsError as exc:
        raise ValueError("backup destination appeared during publication") from exc
    except OSError as exc:
        raise ValueError("cannot atomically publish backup without overwrite") from exc
    temporary.unlink()

def _safe_attachment_name(value: str) -> str:
    raw=str(value)
    path=PurePosixPath(raw)
    if (not raw or "\\" in raw or path.is_absolute() or
            any(part in {"",".",".."} for part in path.parts) or
            path.parts[0] not in {"sources","attachments"}):
        raise ValueError("unsafe backup member path")
    return path.as_posix()

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
        try:
            tmp.write_text(json.dumps(project,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
            _publish_no_replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
        return path
    def list(self, project_id: str):
        return sorted(self.root.glob(f"{project_id}_*.json"), reverse=True)
    def restore(self, path: str|Path):
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("backup must contain an object")
        return data
    def create_package(self, project: dict, project_id: str, *,
                       attachments: Mapping[str,str|Path]|None = None):
        validation=validate_project(project)
        if not validation["valid"]: raise ValueError("cannot backup invalid project")
        if str(project.get("id") or project.get("project_id") or "") != str(project_id):
            raise ValueError("backup project identifier mismatch")
        stamp=time.strftime("%Y%m%d_%H%M%S")
        path=self.root/f"{project_id}_{stamp}.spbackup"
        suffix=1
        while path.exists():
            path=self.root/f"{project_id}_{stamp}_{suffix}.spbackup"
            suffix += 1
        payload=json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        digest=hashlib.sha256(payload).hexdigest()
        revision=(project.get("_meta") or {}).get("version",project.get("revision",0))
        if isinstance(revision,bool) or not isinstance(revision,int) or revision < 0:
            raise ValueError("backup revision must be a non-negative integer")
        members={"project.json":payload}
        for name,source in sorted((attachments or {}).items()):
            safe=_safe_attachment_name(name)
            source=Path(source)
            if source.is_symlink() or not source.is_file():
                raise ValueError("backup attachment must be a regular file")
            if safe in members:
                raise ValueError("duplicate backup member path")
            members[safe]=source.read_bytes()
        files=[{"path":name,"size":len(content),
                "sha256":hashlib.sha256(content).hexdigest()}
               for name,content in sorted(members.items())]
        manifest={"format":BACKUP_FORMAT,"version":BACKUP_VERSION,"project_id":project_id,
                  "schema_version":project.get("schema_version",1),"revision":revision,
                  "revision_status":"committed" if revision else "unversioned",
                  "created_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                  "producer":BACKUP_PRODUCER,
                  "health":{"project_validation":"passed"},
                  "files":files,
                  "sha256":digest}
        tmp=path.with_name(path.name+".tmp")
        try:
            with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:
                for name,content in members.items():
                    z.writestr(name,content)
                z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,sort_keys=True))
            _publish_no_replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
        return path
    def _read_verified_package(self, path: str|Path, *,
                               expected_project_id: str|None = None,
                               minimum_revision: int|None = None):
        try:
            with zipfile.ZipFile(path) as z:
                infos=z.infolist()
                names=[info.filename for info in infos]
                if len(names)!=len(set(names)):
                    raise ValueError("duplicate backup member path")
                if any(((info.external_attr >> 16) & 0o170000) == 0o120000 for info in infos):
                    raise ValueError("backup symbolic links are not allowed")
                manifest=json.loads(z.read("manifest.json").decode())
                version=manifest.get("version")
                if version == BACKUP_VERSION:
                    listed=manifest.get("files")
                    if not isinstance(listed,list) or not listed:
                        raise ValueError("backup file manifest mismatch")
                    listed_names=[]
                    for item in listed:
                        if not isinstance(item,dict) or item.get("path")=="manifest.json":
                            raise ValueError("backup file manifest mismatch")
                        name=item.get("path")
                        if name!="project.json": name=_safe_attachment_name(name)
                        listed_names.append(name)
                    if set(names)!={"manifest.json",*listed_names}:
                        raise ValueError("backup file manifest mismatch")
                    members={name:z.read(name) for name in listed_names}
                else:
                    if set(names)!={"manifest.json","project.json"}:
                        raise ValueError("invalid legacy backup members")
                    members={"project.json":z.read("project.json")}
                payload=members["project.json"]
        except (OSError,zipfile.BadZipFile,KeyError,json.JSONDecodeError,UnicodeDecodeError) as exc:
            raise ValueError("invalid backup package") from exc
        version=manifest.get("version")
        if manifest.get("format")!=BACKUP_FORMAT or version not in {LEGACY_BACKUP_VERSION,BACKUP_VERSION}:
            raise ValueError("unsupported backup format")
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=manifest.get("sha256"):
            raise ValueError("backup checksum mismatch")
        if version == BACKUP_VERSION:
            expected_files=[{"path":name,"size":len(content),
                             "sha256":hashlib.sha256(content).hexdigest()}
                            for name,content in sorted(members.items())]
            if manifest.get("files") != expected_files:
                raise ValueError("backup file manifest mismatch")
            if manifest.get("producer") != BACKUP_PRODUCER or manifest.get("health") != {"project_validation":"passed"}:
                raise ValueError("backup health evidence is invalid")
            revision=manifest.get("revision")
            if isinstance(revision,bool) or not isinstance(revision,int) or revision < 0:
                raise ValueError("backup revision is invalid")
        else:
            revision=0
        project=json.loads(payload.decode())
        if not validate_project(project)["valid"]: raise ValueError("backup integrity validation failed")
        if str(project.get("id","")) != str(manifest.get("project_id","")):
            raise ValueError("backup project identifier mismatch")
        if expected_project_id is not None and str(manifest.get("project_id")) != str(expected_project_id):
            raise ValueError("backup project identifier mismatch")
        payload_revision=(project.get("_meta") or {}).get("version",project.get("revision",0))
        if version == BACKUP_VERSION and payload_revision != revision:
            raise ValueError("backup revision evidence mismatch")
        if version == BACKUP_VERSION and manifest.get("schema_version") != project.get("schema_version",1):
            raise ValueError("backup schema evidence mismatch")
        if minimum_revision is not None:
            if isinstance(minimum_revision,bool) or not isinstance(minimum_revision,int) or minimum_revision < 0:
                raise ValueError("minimum revision is invalid")
            if revision < minimum_revision:
                raise ValueError("backup revision is older than the protected project")
        return project,manifest,members

    def restore_package(self, path: str|Path, *, expected_project_id: str|None = None,
                        minimum_revision: int|None = None):
        project,_,_=self._read_verified_package(
            path,expected_project_id=expected_project_id,
            minimum_revision=minimum_revision)
        return project

    def restore_package_to(self, path: str|Path, destination: str|Path, *,
                           expected_project_id: str|None = None,
                           minimum_revision: int|None = None):
        """Validate first, then materialize into a brand-new staging directory."""
        project,_,members=self._read_verified_package(
            path,expected_project_id=expected_project_id,
            minimum_revision=minimum_revision)
        destination=Path(destination)
        if destination.exists():
            raise ValueError("restore destination must not exist")
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.mkdir()
        restored=destination/"project.json"
        try:
            for name,payload in members.items():
                target=destination/name
                target.parent.mkdir(parents=True,exist_ok=True)
                temporary=target.with_name("."+target.name+".tmp")
                temporary.write_bytes(payload)
                _publish_no_replace(temporary,target)
        except Exception:
            shutil.rmtree(destination)
            raise
        revision=(project.get("_meta") or {}).get("version",project.get("revision",0))
        return {"directory":str(destination),"project_path":str(restored),
                "project_id":str(project.get("id") or project.get("project_id")),
                "revision":revision,"sha256":hashlib.sha256(members["project.json"]).hexdigest(),
                "files":len(members)}
    def prune(self, project_id: str, keep=10):
        keep=max(1,int(keep)); files=self.list(project_id)
        for p in files[keep:]: p.unlink(missing_ok=True)
        return files[:keep]
