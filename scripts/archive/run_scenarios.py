# -*- coding: utf-8 -*-
"""run_scenarios.py - 随机抽取关联人物聚同场景，连续运行 1 小时，重复 3 次。

每次运行：
1. 从 AuvAgents.json 里随机抽 3~4 个互有关联（通讯录相交）的人物；
2. 把他们全部塞进同一场景（以种子人物的初始位置为聚会点）；
3. 用 continuous_runner 跑满 1 模拟小时；
4. 结果（events.jsonl / record_by_scene.md / record_by_person.md）存入独立目录 runs/runN/。

用法：
    python run_scenarios.py            # 默认 3 次，每次 1 小时
    python run_scenarios.py --reps 3 --hours 1
"""
import os, sys, json, random, argparse

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from continuous_runner import run, DEFAULT_BASE, DEFAULT_SPEED

AGENTS_FILE = os.path.join(PROJ, "AuvAgents.json")
RUNS_DIR = os.path.join(PROJ, "runs")


def load_all():
    with open(AGENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    names = [d["name"] for d in data]
    addr = {d["name"]: set(d.get("addressBook", [])) for d in data}
    pos = {d["name"]: d.get("初始位置", d.get("envName", "未知")) for d in data}
    return names, addr, pos


def neighbors_of(name, addr, valid):
    return [m for m in addr.get(name, set()) if m in valid]


def pick_cluster(k, names, addr):
    """随机抽一个种子，沿通讯录做随机游走扩成 k 个互有关联的人物。"""
    seed = random.choice(names)
    cluster = [seed]
    frontier = list(neighbors_of(seed, addr, set(names)))
    random.shuffle(frontier)
    while len(cluster) < k and frontier:
        nxt = frontier.pop(0)
        if nxt in cluster:
            continue
        cluster.append(nxt)
        for nb in neighbors_of(nxt, addr, set(names)):
            if nb not in cluster:
                frontier.append(nb)
        random.shuffle(frontier)
    # 关联人物不足时，补随机人物凑数（仍尽量有关联）
    while len(cluster) < k:
        c = random.choice(names)
        if c not in cluster:
            cluster.append(c)
    return cluster


def main():
    ap = argparse.ArgumentParser(description="随机抽取关联人物聚同场景，连续运行 1 小时，重复 N 次")
    ap.add_argument("--reps", type=int, default=3, help="重复次数（默认 3）")
    ap.add_argument("--hours", type=float, default=1.0, help="每次运行的模拟小时数（默认 1）")
    ap.add_argument("--speed", type=float, default=DEFAULT_SPEED, help="每模拟分钟对应真实秒数")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    names, addr, pos = load_all()
    os.makedirs(RUNS_DIR, exist_ok=True)

    summary = []
    for i in range(1, args.reps + 1):
        k = random.choice([3, 4])
        cluster = pick_cluster(k, names, addr)
        seed = cluster[0]
        scene = pos.get(seed, "未知场景")
        out_dir = os.path.join(RUNS_DIR, f"run{i}")
        os.makedirs(out_dir, exist_ok=True)

        print("\n" + "=" * 60)
        print(f"第 {i}/{args.reps} 次：人物 {cluster}")
        print(f"聚会场景：【{scene}】  输出目录：{out_dir}")
        print("=" * 60)

        run(AGENTS_FILE, base_time=DEFAULT_BASE, speed=args.speed,
            max_hours=args.hours, out_dir=out_dir,
            subset=cluster, common_scene=scene)

        summary.append((i, cluster, scene, out_dir))

    print("\n" + "#" * 60)
    print("全部运行完成。各次独立结果：")
    for i, cluster, scene, out_dir in summary:
        print(f"  run{i}: 人物={cluster}  场景=【{scene}】  目录={out_dir}")
    print("#" * 60)


if __name__ == "__main__":
    main()
