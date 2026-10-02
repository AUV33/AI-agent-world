# -*- coding: utf-8 -*-
import subprocess, re

out = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe'", 'get', 'processid,commandline'],
    capture_output=True, text=True, timeout=20).stdout

killed = []
for line in out.splitlines():
    if 'demo_run.py' in line:
        m = re.search(r'(\d+)\s*$', line.strip())
        if m:
            pid = m.group(1)
            r = subprocess.run(['taskkill', '/f', '/pid', pid],
                               capture_output=True, text=True)
            killed.append((pid, r.returncode, r.stdout.strip()))

print('killed demo_run.py processes:', killed if killed else 'none')
