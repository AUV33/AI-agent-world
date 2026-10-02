# -*- coding: utf-8 -*-
import os, time

def info(p):
    if os.path.exists(p):
        st = os.stat(p)
        return os.path.getsize(p), time.strftime('%H:%M:%S', time.localtime(st.st_mtime))
    return 'missing', '-'

out = r'D:\AI-agent-world\demo_output.txt'
con = r'D:\AI-agent-world\demo_console.log'
t = open(out, encoding='utf-8', errors='ignore').read() if os.path.exists(out) else ''
done = t.count('接下来一小时的动作')
print('agent-rounds done:', done, '/ 12')
print('demo_output.txt   :', info(out))
print('demo_console.log  :', info(con))
