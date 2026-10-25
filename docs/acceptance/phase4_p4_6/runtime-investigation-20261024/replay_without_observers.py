"""Replay preserved revision bytes; inspect only after all commits and reopen."""
import hashlib,json,sqlite3,sys
from pathlib import Path
source=Path(sys.argv[1]);output=Path(sys.argv[2]);roots=[Path(x) for x in sys.argv[3:]]
reader=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)
rows=reader.execute('select project_id,version,created_at,payload from revisions order by version').fetchall()
reader.close();results=[]
for root in roots:
    root.mkdir(parents=True,exist_ok=False)
    for cycle in range(2):
        path=root/('replay-'+str(cycle)+'.db');connection=sqlite3.connect(path)
        connection.executescript('''CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at REAL NOT NULL,payload TEXT NOT NULL);
CREATE TABLE revisions(project_id TEXT NOT NULL,version INTEGER NOT NULL,created_at REAL NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(project_id,version));''')
        for pid,version,created,payload in rows:
            data=json.loads(payload)
            connection.execute('BEGIN IMMEDIATE')
            previous=connection.execute('SELECT version,payload FROM projects WHERE id=?',(pid,)).fetchone()
            if previous:
                assert previous[0]==version-1
                json.loads(previous[1])
            connection.execute('INSERT OR REPLACE INTO projects(id,name,version,updated_at,payload) VALUES(?,?,?,?,?)',(pid,data['name'],version,created,payload))
            connection.execute('INSERT OR REPLACE INTO revisions(project_id,version,created_at,payload) VALUES(?,?,?,?)',(pid,version,created,payload))
            connection.commit()
        connection.close()
        check=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
        integrity=check.execute('pragma integrity_check').fetchall()
        actual=check.execute('select version,cast(payload as blob) from projects').fetchone()
        revisions=check.execute('select count(*) from revisions').fetchone()[0]
        check.close()
        results.append({'path':str(path),'cycles':len(rows),'integrity':integrity,'version':actual[0],'revisions':revisions,'payload_matches_source':actual[1]==rows[-1][3].encode(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
output.write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sqlite':sqlite3.sqlite_version,'mode':'BEGIN IMMEDIATE + original SELECT + original two INSERT OR REPLACE statements + commit; no integrity checks between commits','results':results},indent=2))
print(json.dumps(results))
