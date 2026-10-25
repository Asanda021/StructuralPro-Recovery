"""Calibrate the native extended code on a separate, explicitly moved fixture."""
import sqlite3,json,os
from pathlib import Path

def test_native_dbmoved_code_and_preserved_journal(tmp_path):
    import importlib.util
    # This is deliberately moved test data, never either damaged historical DB.
    path=tmp_path/'calibration.db';moved=tmp_path/'calibration-moved.db'
    con=sqlite3.connect(path);con.execute('create table calibration(value text)');con.commit()
    opened=path.stat();fd=[]
    for f in Path('/proc/self/fd').iterdir():
        try:
            s=f.stat()
            if (s.st_dev,s.st_ino)==(opened.st_dev,opened.st_ino):fd.append({'fd':f.name,'device':s.st_dev,'inode':s.st_ino,'target':os.readlink(f)})
        except OSError:pass
    journal=con.execute('pragma journal_mode').fetchone()[0]
    path.rename(moved)
    try:
        con.execute("insert into calibration values ('explicit synthetic calibration')")
    except sqlite3.Error as e:
        r={'scope':'Intentional synthetic rename only; NOT historical root-cause proof','sqlite_errorcode':e.sqlite_errorcode,'sqlite_errorname':e.sqlite_errorname,'message':str(e),'opened_identity':[opened.st_dev,opened.st_ino],'live_fds_before':fd,'journal_mode':journal,'path_exists_at_error':path.exists(),'moved_identity':[moved.stat().st_dev,moved.stat().st_ino],'companion_files':[str(p) for p in tmp_path.glob('*')],'live_fds_at_error':[]}
        for f in fd:
            p=Path('/proc/self/fd')/f['fd'];s=p.stat();r['live_fds_at_error'].append({'fd':f['fd'],'target':os.readlink(p),'device':s.st_dev,'inode':s.st_ino})
        assert e.sqlite_errorcode==sqlite3.SQLITE_READONLY_DBMOVED==1032
        assert e.sqlite_errorname=='SQLITE_READONLY_DBMOVED'
    else:raise AssertionError('Native SQLite did not reject the intentionally moved file')
    finally:con.close()
    with sqlite3.connect(moved) as fresh:
        assert fresh.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert fresh.execute('select count(*) from calibration').fetchone()[0]==0
    Path('docs/acceptance/phase4_p4_6/closure-20261025/dbmoved-calibration.json').write_text(json.dumps(r,indent=2))
