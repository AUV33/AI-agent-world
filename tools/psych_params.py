# -*- coding: utf-8 -*-
"""psych_params.py - 从人设【推导】心理引擎参数（透明、可复核、零依赖、零 LLM）。

为什么要有这个工具
  「每个人都是主角」要求每个角色有自己的一套心理参数；但手塞数字无法复核，
  也无法回答"凭什么 AUV 的 k_sup 是 14"。
  这里的做法：先把角色读成【五个轴】的分数（每轴都写清 persona 依据），再用固定公式映射到 11 个参数。
  —— 轴分是我读文本的判断（可被人推翻、可逐条改），映射是死公式（谁都能重算）。

五个轴（各 0~1，越高越强）
  suppress     压抑：不说、憋着、怕让人失望
  irritability 易激惹：脾气、粗暴、一点就炸
  tolerance    耐受/克制：职业克制、稳重、看场合
  rumination   反刍/记仇：记很久、放不下
  volatility   心境波动：起伏大、敏感

用法
  python tools/psych_params.py --check data/AuvAgents.json    # 数据与推导是否一致（CI 用）
  python tools/psych_params.py --apply data/AuvAgents.json    # 把推导结果写回角色包
  python tools/psych_params.py --show                          # 打印表：轴 / 参数 / 依据
"""
import io
import os
import re
import sys
import json
import argparse

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
from core.psychology import DEFAULTS_PERSONA

# ——— 轴打分表：每一条都附 persona 依据（依据来自 data/AuvAgents.json 的 persona / persona_cognitive）———
# 顺序：suppress, irritability, tolerance, rumination, volatility
AXES = {
    "AUV": ((0.85, 0.15, 0.60, 0.70, 0.55),
            "性格温和＋内心吐槽能力强＋最怕让别人失望 ⇒ 高压抑；被多任务轰炸会眩晕 ⇒ 中等反刍"),
    "至": ((0.45, 0.50, 0.35, 0.60, 0.60),
           "外表凶巴巴、耳朵一红就露馅 ⇒ 嘴硬心软；直率但内心细腻 ⇒ 压抑中等、波动偏高"),
    "sagi": ((0.25, 0.40, 0.30, 0.30, 0.80),
             "热情外向、像颗小炮弹 ⇒ 不压抑；怕被落下、故意闹腾 ⇒ 心境波动大、不记仇"),
    "黑毛黑框厨": ((0.80, 0.20, 0.55, 0.75, 0.70),
               "内向害羞＋表面维持优雅＋内心容易慌乱 ⇒ 高压抑高波动；会紧张到绞文件夹"),
    "躺啊堂": ((0.50, 0.20, 0.60, 0.40, 0.35),
             "懒洋洋、打哈欠是常态、社交场合淡定 ⇒ 低波动；只对创作起劲"),
    "蜂兵老师": ((0.50, 0.25, 0.85, 0.35, 0.30),
               "教学严谨、目光锐利、对学生严格但有分寸 ⇒ 高耐受；职业角色须克制"),
    "易先生": ((0.60, 0.30, 0.55, 0.50, 0.45),
             "大龄剩男、在网上被人围着问 ⇒ 压抑中高；看得开但也上心"),
    "3A": ((0.55, 0.35, 0.80, 0.45, 0.35),
           "公司老板、3D艺术家、资助又算计 ⇒ 高耐受（谈事情）；惜才但留台阶"),
    "AUV父亲": ((0.35, 0.90, 0.20, 0.70, 0.75),
              "性格粗暴＋离婚 ⇒ 极高易激惹、极低耐受；怕儿子被骗、反复想 ⇒ 高反刍"),
    "日本签证官": ((0.40, 0.20, 0.90, 0.25, 0.20),
                "按标准办事、长期审理材料 ⇒ 极高耐受、极低波动；不记个人恩怨"),
    "日本电子专门学校admission面试官": ((0.45, 0.20, 0.80, 0.30, 0.30),
                                   "远程面试、靠材料和答话判断人 ⇒ 高耐受；会多问一句（不冷）"),
    "AUV小姨": ((0.40, 0.50, 0.50, 0.60, 0.65),
              "看什么先算风险、劝得急 ⇒ 易激惹中等；担心外甥 ⇒ 反刍与波动偏高"),
    "AUV姨父": ((0.30, 0.25, 0.70, 0.20, 0.35),
              "觉得生活该尽情体验、生意最重要 ⇒ 低压抑低反刍；松弛"),
}

# ——— 映射：轴 → 11 个参数（死公式，写死在这里，谁都能重算）———
H = 3600.0


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def derive(axes):
    sup, irr, tol, rum, vol = axes
    p = {
        "k_sup": round(6.0 + 12.0 * sup, 2),                              # 压抑累积
        "k_cost": round(0.4 + 1.1 * sup, 3),                              # 成本（耐心消耗）
        "kappa": round(0.95 - 0.70 * sup, 3),                             # 表达泄压
        "beta": round(_clamp(0.65 - 0.35 * irr + 0.10 * tol, 0.20, 0.65), 3),
        "alpha": round(0.08 + 0.40 * irr, 3),                             # 阈限下调
        "theta0": round(_clamp(45.0 + 45.0 * tol - 20.0 * irr, 35.0, 90.0), 1),
        "tau_F": round(3 * H + 15 * H * rum, 0),                          # 挫折衰减
        "tau_scale": round(0.50 + 1.40 * rum, 2),                         # 情绪持续（记仇）
        "tau_theta": round(6 * H + 18 * H * (1.0 - tol), 0),               # 阈限回升
        "k_mood": round(0.03 + 0.15 * vol, 3),                            # 心境推动
        "tau_mood": round(6 * H + 42 * H * (1.0 - vol), 0),                # 心境回落
    }
    return p


def _params_equal(a, b):
    keys = list(DEFAULTS_PERSONA.keys())
    if not a:
        return False
    return all(abs(float(a.get(k, DEFAULTS_PERSONA[k])) - float(b[k])) < 1e-9 for k in keys)


def _load(p):
    return json.load(io.open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default=None, help="校验角色包里的 psych 与推导一致")
    ap.add_argument("--apply", default=None, help="把推导结果写回角色包")
    ap.add_argument("--show", action="store_true", help="打印轴 / 参数 / 依据")
    a = ap.parse_args()

    if a.show or (not a.check and not a.apply):
        print("%-24s %s" % ("角色", "轴 sup/irr/tol/rum/vol"))
        for n, (ax, why) in AXES.items():
            print("%-24s %s" % (n, " ".join("%.2f" % x for x in ax)))
            print("     依据：%s" % why)
        print()
        keys = list(DEFAULTS_PERSONA.keys())
        print("%-24s %s" % ("角色", " ".join("%9s" % k for k in keys)))
        print("%-24s %s" % ("默认", " ".join("%9s" % DEFAULTS_PERSONA[k] for k in keys)))
        for n, (ax, _) in AXES.items():
            p = derive(ax)
            print("%-24s %s" % (n, " ".join("%9s" % p[k] for k in keys)))
        never = [k for k in keys if all(derive(ax)[k] == DEFAULTS_PERSONA[k] for ax, _ in AXES.values())]
        print("\n仍与默认完全相同的参数：%s" % ("、".join(never) if never else "(无)"))
        return 0

    if a.check:
        data = _load(a.check)
        bad = []
        for d in data:
            ax = AXES.get(d["name"])
            if not ax:
                continue
            if not _params_equal(d.get("psych"), derive(ax[0])):
                bad.append(d["name"])
        if bad:
            print("[x] 这些角色的 psych 与推导不一致：%s" % "、".join(bad))
            return 1
        print("[OK] %s：%d 个角色的 psych 与推导一致" % (os.path.basename(a.check), len(AXES)))
        return 0

    if a.apply:
        p = a.apply
        text = io.open(p, encoding="utf-8").read()
        data = json.loads(text)
        SRC = "axes_v1（五轴打分→固定公式推导；轴分依据见 tools/psych_params.py，待人复核）"
        lines = text.split("\n")

        # 按【角色对象】切块处理：块内只认自己的 psych 行。
        # （教训：早先版本在全文里向后找 "psych" 行，会扫到下一个角色的字段、写错人；
        #   --check 当场抓出 8 处不一致。工具本身必须先对，才谈得上数据对。）
        out, i, n = [], 0, 0
        while i < len(lines):
            if lines[i] == "  {":                       # 一个角色对象的开始
                j = i + 1
                while j < len(lines) and lines[j] not in ("  },", "  }"):
                    j += 1
                block = lines[i:j + 1]
                name = None
                for b in block:
                    mm = re.match(r'^    "name": "(.+)",$', b)
                    if mm:
                        name = mm.group(1)
                        break
                if name in AXES:
                    psy = dict(derive(AXES[name][0]))
                    psy["_source"] = SRC
                    psy["_axes"] = dict(zip(("suppress", "irritability", "tolerance",
                                             "rumination", "volatility"), AXES[name][0]))
                    blob = '    "psych": %s,' % json.dumps(psy, ensure_ascii=False)
                    new_block, done = [], False
                    for b in block:
                        if b.lstrip().startswith('"psych"'):
                            if not done:
                                new_block.append(blob)
                                done = True
                            continue                        # 多余的旧 psych 行一律丢掉
                        new_block.append(b)
                    if not done:                            # 原本没有 psych：插在 persona 行之后
                        k = next((idx for idx, b in enumerate(new_block)
                                  if b.startswith('    "persona":')), 0)
                        new_block.insert(k + 1, blob)
                    block = new_block
                    n += 1
                out.extend(block)
                i = j + 1
                continue
            out.append(lines[i])
            i += 1

        new_text = "\n".join(out)
        new = json.loads(new_text)
        assert len(new) == len(data), "角色数变了"
        by_old = {d["name"]: d for d in data}
        for d in new:
            o = by_old[d["name"]]
            for key in o:
                if key == "psych":
                    continue
                assert o[key] == d[key], "%s 的 %s 被改动" % (d["name"], key)
        for d in new:
            if d["name"] in AXES:
                assert _params_equal(d.get("psych"), derive(AXES[d["name"]][0])), \
                    "%s 写回后与推导不一致" % d["name"]
        io.open(p, "w", encoding="utf-8", newline="\n").write(new_text)
        print("已写回 %s：%d 个角色的 psych（11 个参数全部由轴推导，写后自校验通过）" % (p, n))
        return 0


if __name__ == "__main__":
    sys.exit(main())
