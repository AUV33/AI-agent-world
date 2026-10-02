# -*- coding: utf-8 -*-
import subprocess, sys, os, time, re, glob

PROJ = os.path.dirname(os.path.abspath(__file__))
FOCUS = ['坂田美优', '山田健太', '坂田美优妈妈', '山田阳菜', '照相馆老板']
N_REPS = 5
N_ROUNDS = 5


def clear_memory():
    for pat in ['memory.db', 'memory.db-journal', 'memory.db-wal', 'memory.db-shm']:
        p = os.path.join(PROJ, pat)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    for name in FOCUS:
        for pat in [f'emotion_{name}.json', f'life_{name}.json', f'thinking_{name}.jsonl']:
            p = os.path.join(PROJ, pat)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def main():
    status_path = os.path.join(PROJ, 'focus_reps_status.txt')
    with open(status_path, 'w', encoding='utf-8') as sf:
        sf.write('开始 5 次独立重跑 @ %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))

    for rep in range(1, N_REPS + 1):
        clear_memory()
        out_name = 'focus_rep%d.txt' % rep
        out_path = os.path.join(PROJ, out_name)
        spawn_log = os.path.join(PROJ, 'focus_rep%d_spawn.log' % rep)
        t0 = time.time()
        with open(spawn_log, 'w', encoding='utf-8') as lf:
            try:
                p = subprocess.run(
                    [sys.executable, 'run_one.py', str(N_ROUNDS), 'focus_agents.json', out_name],
                    cwd=PROJ, stdout=lf, stderr=lf, timeout=60 * 60)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = -9
        dt = int(time.time() - t0)
        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        errs = 0
        rmarks = 0
        if os.path.exists(out_path):
            s = open(out_path, encoding='utf-8', errors='ignore').read()
            rmarks = sum(len(re.findall(r'\[第%d轮' % i, s)) for i in range(1, N_ROUNDS + 1))
            errs = len(re.findall(r'\[ERROR\]', s))
        with open(status_path, 'a', encoding='utf-8') as sf:
            sf.write('rep%d: exit=%s 用时=%ds 输出=%s(%dB) 轮标记=%d 报错=%d @ %s\n'
                     % (rep, rc, dt, out_name, size, rmarks, errs, time.strftime('%H:%M:%S')))
        print('rep%d done exit=%s marks=%d errs=%d' % (rep, rc, rmarks, errs))

    with open(status_path, 'a', encoding='utf-8') as sf:
        sf.write('全部完成 @ %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))


if __name__ == '__main__':
    main()
