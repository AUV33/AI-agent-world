# -*- coding: utf-8 -*-
"""make_readable.py - 把原始模拟日志转成人类易读的「剧情本」。

用法：
    python make_readable.py                  # 转换 demo_output.txt -> 剧情记录.md
    python make_readable.py 某日志.txt 输出.md
"""
import os, sys, re

PROJ = os.path.dirname(os.path.abspath(__file__))


def extract(body, start_marker, end_marker):
    sm = re.search(re.escape(start_marker), body)
    if not sm:
        return ""
    s = sm.end()
    if end_marker:
        em = re.search(re.escape(end_marker), body[s:])
        e = s + em.start() if em else len(body)
    else:
        e = len(body)
    # 清理：节号残留、首尾粗体星号、分隔线、空白
    result = body[s:e].strip()
    result = re.sub(r'\s*\d+\.\s*$', '', result)  # 去掉结尾 "2." / "3." 节号
    result = re.sub(r'^\*+', '', result)          # 去掉开头 **（粗体残留）
    result = re.sub(r'\*+$', '', result)          # 去掉结尾 **
    result = re.sub(r'-{10,}\s*$', '', result)    # 去掉结尾的分隔线 ----
    return result.strip()


def parse_log(text):
    # 真正的轮次 = 被分隔线 '=' 夹住的标题行；记忆文本里的"第x轮"不会被误判
    parts = re.split(r'=+\s*(第\d+轮\s*第\d+天\s*\d{2}:\d{2})\s*=+', text)
    # parts: [前导, 标题1, 块1, 标题2, 块2, ...]
    rounds = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        block = parts[i + 1] if i + 1 < len(parts) else ""
        # 角色块以 "[第x轮 ...] 名字 位置 ：" 分割
        char_blocks = re.split(r'\[' + re.escape(header) + r'\]\s*', block)
        chars = []
        for cb in char_blocks[1:]:
            nm = re.match(r'(\S+?)\s*(\S+?)\s*：\s*\n', cb)
            if not nm:
                continue
            name, loc = nm.group(1), nm.group(2)
            body = cb[nm.end():]
            think = extract(body, '思考【思考内容】', '更新记忆')
            mem = extract(body, '更新记忆【新的记忆】', '接下来一小时的动作')
            act = extract(body, '接下来一小时的动作', '-' * 10)
            chars.append({'name': name, 'loc': loc, 'think': think,
                          'mem': mem, 'act': act})
        rounds.append({'header': header, 'chars': chars})
    return rounds


def find_interactions(act):
    """从动作文本里抽出角色间的互动（发消息 / 移动）。"""
    out = []
    for frm, msg in re.findall(r'向【(.+?)】发送【(.+?)】', act):
        out.append(('msg', frm, msg))
    for frm, msg in re.findall(r'向(.+?)发送【(.+?)】', act):
        out.append(('msg', frm, msg))
    for to in re.findall(r'我要前往【(.+?)】', act):
        out.append(('move', to, ''))
    return out


def render(rounds, title="模拟剧情本"):
    lines = [f"# {title}", ""]
    lines.append("> 本文件由 `make_readable.py` 从原始日志自动生成，按场次整理，互动已高亮。\n")
    for r in rounds:
        lines.append(f"## {r['header']}")
        lines.append("")
        for c in r['chars']:
            lines.append(f"### {c['name']}（{c['loc']}）")
            lines.append("")
            if c['think']:
                lines.append(f"> **内心**：{c['think']}")
                lines.append("")
            if c['act']:
                lines.append(f"**行动**：{c['act']}")
                lines.append("")
            inter = find_interactions(c['act'])
            if inter:
                lines.append("**互动：**")
                for kind, a, b in inter:
                    if kind == 'msg':
                        lines.append(f"- 💬 给 **{a}** 发了消息：{b}")
                    else:
                        lines.append(f"- 🚶 前往 **{a}**")
                lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, 'demo_output.txt')
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PROJ, '剧情记录.md')
    with open(src, 'r', encoding='utf-8') as f:
        text = f.read()
    rounds = parse_log(text)
    out = render(rounds)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(out)
    n_rounds = len(rounds)
    n_chars = sum(len(r['chars']) for r in rounds)
    print(f"已生成：{dst}")
    print(f"共 {n_rounds} 轮 / {n_chars} 条角色记录")


if __name__ == "__main__":
    main()
