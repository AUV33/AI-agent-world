#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比 runs/run1~3 三次运行的剧情相似度。
- 角色/场景重合
- 字符 bigram 的 Jaccard 相似度（剧情文本重合度）
- 跨轮复现的"签名短语"（人设/口头禅一致性）
"""
import os, re, json

PROJ = os.path.dirname(os.path.abspath(__file__))
RUNS = ["run1", "run2", "run3"]


def read_scene(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract(path):
    txt = read_scene(path)
    # 场景
    m = re.search(r"##\s*📍\s*(.+)", txt)
    scene = m.group(1).strip() if m else "?"
    # 角色（**名字**）
    chars = re.findall(r"\*\*(.+?)\*\*", txt)
    chars = [c for c in chars if c not in ("",)]
    # 去掉 markdown 标记，保留剧情正文用于 bigram
    body = re.sub(r"#.*", "", txt)
    body = re.sub(r"\*\*.+?\*\*", "", body)
    body = re.sub(r"-\s*\[.*?\]", "", body)
    body = re.sub(r"[#\*\-→\[\]【】]", "", body)
    return scene, chars, body


def bigrams(s):
    # 仅取 CJK 字符做 bigram，过滤标点/空格
    cjk = re.findall(r"[\u4e00-\u9fff]", s)
    return set(zip(cjk, cjk[1:])) if len(cjk) > 1 else set()


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# 签名短语（跨轮可能复现的人设/口头禅/道具）
SIGNATURES = [
    "新号别搞老号也别搞", "超——级", "周报", "建模", "人体线稿", "拓扑",
    "中长发", "iPad", "温润", "站桩", "木椅", "徽章", "迷你世界",
    "蜂兵老师", "监督", "3D艺术", "笋干", "奶粉", "签证", "叫号",
    "闭眼", "揉眉心", "折角", "贴纸", "眩晕",
]


def main():
    data = {}
    for r in RUNS:
        p = os.path.join(PROJ, "runs", r, "record_by_scene.md")
        scene, chars, body = extract(p)
        data[r] = {
            "scene": scene,
            "chars": chars,
            "body": body,
            "bg": bigrams(body),
        }

    print("=" * 60)
    print("一、角色 / 场景 重合")
    print("=" * 60)
    for r in RUNS:
        uniq = sorted(set(data[r]["chars"]))
        print(f"  {r}: 场景【{data[r]['scene']}】  角色({len(uniq)})={uniq}")
    all_chars = {c for r in RUNS for c in set(data[r]["chars"])}
    print(f"  全部出现过的角色：{sorted(all_chars)}")
    # 角色重合矩阵
    print("\n  角色 Jaccard 重合矩阵：")
    print("        " + "  ".join(f"{r:>6}" for r in RUNS))
    for a in RUNS:
        row = []
        for b in RUNS:
            sa, sb = set(data[a]["chars"]), set(data[b]["chars"])
            row.append(f"{jaccard(sa, sb):.2f}")
        print(f"  {a:>4}  " + "  ".join(f"{v:>6}" for v in row))

    print("\n" + "=" * 60)
    print("二、剧情文本 bigram Jaccard 相似度（越高越像）")
    print("=" * 60)
    print("        " + "  ".join(f"{r:>6}" for r in RUNS))
    for a in RUNS:
        row = []
        for b in RUNS:
            row.append(f"{jaccard(data[a]['bg'], data[b]['bg']):.3f}")
        print(f"  {a:>4}  " + "  ".join(f"{v:>6}" for v in row))

    print("\n" + "=" * 60)
    print("三、跨轮复现的签名短语（人设/口头禅一致性）")
    print("=" * 60)
    for sig in SIGNATURES:
        hits = [r for r in RUNS if sig in data[r]["body"]]
        if hits:
            print(f"  「{sig}」出现在：{hits}")

    # 输出 JSON 便于二次处理
    out = {r: {"scene": data[r]["scene"], "chars": sorted(set(data[r]["chars"]))}
           for r in RUNS}
    with open(os.path.join(PROJ, "runs", "compare.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n已写出 runs/compare.json")


if __name__ == "__main__":
    main()
