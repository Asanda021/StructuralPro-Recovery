import html,json,re,subprocess,sys
from pathlib import Path
run=sys.argv[1]; out=Path('/workspace/p6-observe-'+run+'.html')
subprocess.run(['curl','-fsSL','https://github.com/Asanda021/StructuralPro-Recovery/actions/runs/'+run+'?observe='+sys.argv[2],'-o',str(out)],check=True)
s=html.unescape(out.read_text()); result={'run':run,'status':re.findall(r'Status</span>\s*<[^>]+>([^<]+)',s),'reports':[]}
for pattern in [r'[{]"file": [^{}]+[}]',r'<div>({"source_sha".*?)</div>',r'<div>({"verified".*?)</div>',r'<div>({"artifact".*?)</div>']:
 for x in re.findall(pattern,s):
  try: result['reports'].append(json.loads(x))
  except ValueError: pass
result['artifacts']=re.findall(r'<span class="text-bold color-fg-default"[^>]*>\s*(p6-[^<]+?)\s*</span>.*?id="artifact-(\d+)-hash"',s,re.S)
result['digests']=re.findall(r'sha256:([0-9a-f]{64})',s)
Path('/workspace/p6-observe-'+run+'.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,ensure_ascii=False))
