# -*- coding: utf-8 -*-
"""monitor.py - 轮询 run_remaining_status.txt，检测到 ALL DONE 后汇总并退出。"""
import os, sys, time, re
PROJ = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(PROJ, 'run_remaining_status.txt')
SUMMARY = os.path.join(PROJ, 'monitor_summary.txt')
WORLDS = [('Japan','run_japan.txt'),('Jec','run_jec.txt'),
          ('Malaya','run_malaya.txt'),('demo','run_demo.txt')]

def main_proc_alive():
    # run_remaining.py 是父进程；用状态文件判断更稳，这里仅辅助
    return True

def summarize():
    lines = []
    total_ok = total_err = 0
    for name, lf in WORLDS:
        p = os.path.join(PROJ, lf)
        if not os.path.exists(p):
            lines.append(f"{name}: 无日志"); continue
        s = open(p, encoding='utf-8', errors='ignore').read()
        r1 = len(re.findall(r'\[第1轮', s)); r2 = len(re.findall(r'\[第2轮', s)); r3 = len(re.findall(r'\[第3轮', s))
        ok = len(re.findall(r'【发送消息成功】', s))
        err = len(re.findall(r'\[ERROR\]', s))
        total_ok += ok; total_err += err
        lines.append(f"{name:8s} size={os.path.getsize(p):8d} R1={r1} R2={r2} R3={r3} 发送={ok} ERR={err}")
    lines.append(f"TOTAL 发送={total_ok} ERR={total_err}")
    return "\n".join(lines)

if __name__ == '__main__':
    start = time.time()
    while True:
        if os.path.exists(STATUS):
            st = open(STATUS, encoding='utf-8', errors='ignore').read()
            if 'ALL DONE' in st:
                msg = f"[{time.strftime('%H:%M:%S')}] ALL DONE detected after {(time.time()-start)/60:.0f} min\n" + summarize()
                open(SUMMARY, 'w', encoding='utf-8').write(msg)
                print(msg)
                break
            # 主进程异常退出但没 ALL DONE
            if ('END ' in st) and ('ALL DONE' not in st) and time.time()-start > 60:
                # 检查是否所有 world 都 END 了却没 ALL DONE（理论不会）
                pass
        if time.time() - start > 6*3600:
            open(SUMMARY, 'w', encoding='utf-8').write("monitor timeout (6h)\n"+summarize())
            break
        time.sleep(120)
