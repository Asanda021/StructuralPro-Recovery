"""External one-second observations; never changes the tested process."""
import json,sys,time
from pathlib import Path
import psutil
p=psutil.Process(int(sys.argv[1]))
with open(sys.argv[2],'w') as out:
    while p.is_running() and p.status()!=psutil.STATUS_ZOMBIE:
        try:
            row={'wall':time.time(),'monotonic':time.monotonic(),
                 'cpu_seconds':sum(p.cpu_times()[:2]),'rss':p.memory_info().rss,
                 'threads':p.num_threads(),'host_load':psutil.getloadavg(),
                 'cgroup_cpu_stat':Path('/sys/fs/cgroup/cpu.stat').read_text()}
            out.write(json.dumps(row)+'\n');out.flush()
        except psutil.NoSuchProcess:break
        time.sleep(1)
