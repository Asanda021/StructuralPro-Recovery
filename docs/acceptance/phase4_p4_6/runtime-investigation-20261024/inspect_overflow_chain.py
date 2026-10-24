"""Read-only inspection of the preserved single-row projects table."""
import hashlib,json,sqlite3,sys
from pathlib import Path
path=Path(sys.argv[1]);connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
root=connection.execute("select rootpage from sqlite_master where name='projects'").fetchone()[0]
version,actual=connection.execute('select version,cast(payload as blob) from projects').fetchone()
expected=connection.execute('select cast(payload as blob) from revisions where version=?',(version,)).fetchone()[0]
integrity=connection.execute('pragma integrity_check').fetchall();connection.close()
raw=path.read_bytes();size=int.from_bytes(raw[16:18],'big');usable=size-raw[20]
page=raw[(root-1)*size:root*size]
assert page[0]==13 and int.from_bytes(page[3:5],'big')==1
offset=int.from_bytes(page[8:10],'big')
def varint(data,pos):
    value=0
    for i in range(9):
        x=data[pos+i]
        if i==8:return (value<<8)|x,pos+i+1
        value=(value<<7)|(x&127)
        if not x&128:return value,pos+i+1
length,pos=varint(page,offset);rowid,pos=varint(page,pos)
minimum=((usable-12)*32//255)-23;maximum=usable-35
local=minimum+(length-minimum)%(usable-4)
if local>maximum:local=minimum
record=page[pos:pos+local];next_page=int.from_bytes(page[pos+local:pos+local+4],'big')
chain=[];remaining=length-local
while remaining:
    assert 0<next_page<=len(raw)//size
    chain.append(next_page);part=raw[(next_page-1)*size:next_page*size]
    take=min(remaining,usable-4);record+=part[4:4+take];remaining-=take
    next_page=int.from_bytes(part[:4],'big')
assert record[-len(actual):]==actual, 'Decoded record must agree with SQLite CAST(payload AS BLOB)'
result={'file_sha256':hashlib.sha256(raw).hexdigest(),'version':version,'rootpage':root,'page_size':size,'record_bytes':length,'json_bytes':len(actual),'local_bytes':local,'json_record_offset':len(record)-len(actual),'overflow_chain':chain,'duplicate_pages':sorted({p for p in chain if chain.count(p)>1}),'first_difference':next((i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y),None),'different_bytes':sum(x!=y for x,y in zip(actual,expected)),'integrity':integrity,'mode':'read-only; no recovery or source writes'}
Path(sys.argv[2]).write_text(json.dumps(result,indent=2));print(json.dumps(result))
