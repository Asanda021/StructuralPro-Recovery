# Replay snapshot: source probe ran locally on efaab3c5; paths adjusted for reproducibility. Not a product module.
import urllib.request,urllib.parse,hashlib,re,json
from pathlib import Path
repo='buildingsmart-community/Community-Sample-Test-Files';rev='7ddf57a201f88a0c213d5322b02ed15e94a60a40'
paths=['IFC 4.0.2.1 (IFC 4)/Example project location/example project location.ifc','IFC 4.0.2.1 (IFC 4)/ISO Spec archive/wall-with-opening-and-window.ifc','IFC 4.0.2.1 (IFC 4)/ISO Spec archive/surface-model.ifc']
result=[]
for i,path in enumerate(paths):
 row={'source_repository':repo,'source_commit':rev,'source_path':path,'source_license':'CC BY 4.0','status':'NOT_DOWNLOADED'};result.append(row)
 try:
  suffix='/'+repo+'/'+rev+'/'+urllib.parse.quote(path)
  pointer=urllib.request.urlopen('https://raw.githubusercontent.com'+suffix,timeout=40).read()
  oid=re.search(rb'oid sha256:([a-f0-9]{64})',pointer).group(1).decode();size=int(re.search(rb'size (\d+)',pointer).group(1))
  assert size<=10*1024*1024
  with urllib.request.urlopen('https://media.githubusercontent.com/media'+suffix,timeout=60) as response:data=response.read(10*1024*1024+1)
  assert len(data)==size and hashlib.sha256(data).hexdigest()==oid
  Path('/tmp/p6-community-audit/'+str(i)+'.ifc').write_bytes(data)
  row.update(status='PINNED_LFS_BYTES_VERIFIED',sha256=oid,bytes=size,pointer_git_blob_sha1=hashlib.sha1(b'blob '+str(len(pointer)).encode()+b'\0'+pointer).hexdigest())
 except Exception as e:row.update(status='SOURCE_ACCESS_BLOCKED',error_class=type(e).__name__)
 print(json.dumps(row),flush=True)
Path('/tmp/p6-community-audit/sources.json').write_text(json.dumps(result,indent=2))
