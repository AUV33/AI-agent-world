# -*- coding: utf-8 -*-
import subprocess, sys, os, time

PROJ = os.path.dirname(os.path.abspath(__file__))
log = os.path.join(PROJ, 'five_reps_launcher.log')

p = subprocess.Popen(
    [sys.executable, 'run_five_reps.py'],
    cwd=PROJ,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
with open(log, 'w', encoding='utf-8') as f:
    f.write('launched pid=%d @ %s\n' % (p.pid, time.strftime('%Y-%m-%d %H:%M:%S')))
print('launched five-reps runner pid=%d' % p.pid)
