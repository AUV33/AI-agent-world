# -*- coding: utf-8 -*-
import os, re, time, sys

PROJ = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(PROJ, 'focus_reps_status.txt')
N_REPS = 5
POLL = 30
STUCK_LIMIT = 25 * 60

last_grow = time.time()
last_size = 0
done = False

print('monitor started, watching focus_reps_status.txt ...')
while True:
    total_size = 0
    total_marks = 0
    errs = 0
    for rep in range(1, N_REPS + 1):
        fp = os.path.join(PROJ, 'focus_rep%d.txt' % rep)
        if os.path.exists(fp):
            sz = os.path.getsize(fp)
            total_size += sz
            s = open(fp, encoding='utf-8', errors='ignore').read()
            total_marks += sum(len(re.findall(r'\[第%d轮' % i, s)) for i in range(1, 6))
            errs += len(re.findall(r'\[ERROR\]', s))

    reps_done = 0
    if os.path.exists(STATUS):
        with open(STATUS, encoding='utf-8', errors='ignore') as f:
            txt = f.read()
        reps_done = len(re.findall(r'^rep\d+:.*exit=', txt, re.M))
        if '全部完成' in txt:
            done = True

    if total_size > last_size:
        last_grow = time.time()
        last_size = total_size

    stuck = (time.time() - last_grow) > STUCK_LIMIT
    print('[%s] reps_done=%d/%d total_marks=%d errs=%d size=%dB %s'
          % (time.strftime('%H:%M:%S'), reps_done, N_REPS, total_marks, errs, total_size, 'STUCK!' if stuck else ''))

    if done or reps_done >= N_REPS or stuck:
        verdict = 'DONE' if (done or reps_done >= N_REPS) else 'STUCK'
        with open(os.path.join(PROJ, 'focus_reps_done.txt'), 'w', encoding='utf-8') as f:
            f.write('%s reps_done=%d total_marks=%d errs=%d @ %s\n'
                    % (verdict, reps_done, total_marks, errs, time.strftime('%Y-%m-%d %H:%M:%S')))
        print('monitor exit: %s' % verdict)
        sys.exit(0)

    time.sleep(POLL)
