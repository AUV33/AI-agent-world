# -*- coding: utf-8 -*-
"""
character_generator.py —— 角色详细人设生成器（创建角色 / 补全人设）
=====================================================================
用法：
    # 1) 创建角色（生成一份详细人设）
    python character_generator.py create "张伟" --info "17岁，高二(3)班学生，302寝室7号床，喜欢打游戏"
        [--extra 补充说明] [--loc 初始位置] [--addr 通讯录,逗号分隔]
        [--out schoolAgents.json] [--preview]

    # 2) 补全人设（读取现有设定，AI 扩写增强）
    python character_generator.py complete --file schoolAgents.json --name 陈子墨 [--preview]

    # 3) 推荐主流程：优先本地生成，不满意再用 AI 按要求扩写
    python character_generator.py generate "张伟" --info "17岁，懒散，爱打游戏"
        [--enhance "扩写要求，如：性格再鲜明点，多写具体事例"]
        [--loc 初始位置] [--addr 通讯录,逗号分隔] [--out schoolAgents.json] [--preview]

    # 4) 本地自动补全（仅本地，不调用 AI，秒出结果）
    python character_generator.py autofill "张伟" --info "17岁，懒散，爱打游戏，爱吹牛"
        [--loc 初始位置] [--addr 通讯录,逗号分隔] [--out schoolAgents.json] [--preview]

    # 5) --preview：只打印不写入；不带 --out / 不指定写入时默认只打印

人设风格：贴近现实、真实、不完美、包含劣根性——这是所有人的共性，不分年龄身份。
=====================================================================
"""
import sys
import os
import json
import re

PROJ = r"D:\致敬传奇AI项目"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
os.chdir(PROJ)

from caller import call_model

FORMAT_GUIDE = (
    "输出格式：开头一句“你是「名字」，X岁，……（身份介绍）”；"
    "然后分段落，段落标题直接用【性格】【劣根性】【自我与思考】【说话风格】【兴趣爱好】【对室友】【禁忌】【记忆】【手机】这样的格式，不要加粗、不要星号、不要任何markdown符号。"
    "每个段落2到4句话，用中文，口语化、接地气。"
)


def _extract(text):
    return text.strip()


def gen_create(name, info, extra=""):
    is_adult = any(k in info for k in ("老师", "教师", "教练", "主任", "校长", "职员", "保安", "阿姨", "辅导员"))
    if is_adult:
        guide = ("输出格式：开头一句“你是「名字」，……（身份介绍）”；然后分段落："
                 "【性格】【劣根性】【职业习惯】【说话风格】【人际关系】【禁忌】【记忆】。"
                 "每个段落2到4句话，用中文，口语化、接地气。")
        user = (
            f"请为以下角色创作一份详细人设。\n要求：\n"
            f"1. 这是一个有血有肉的成年人（老师/教练/教职工），不要完美；"
            f"必须写出他根子上的【劣根性】（如偏心、爱面子、双标、怕麻烦、偷懒、摆架子、记仇、虚荣、说一套做一套、推卸责任等），至少写3条，每条注明体现程度与触发条件（什么场合暴露、对谁暴露、什么场合收敛）；\n"
            f"2. {guide}\n"
            f"3. 他是明远中学的教职工，人设要符合教师/教练身份，贴近真实校园；\n"
            f"角色基本信息：\n名字：{name}\n简要设定：{info}\n"
            + (f"补充说明：{extra}\n" if extra else "")
        )
    else:
        user = (
            f"请为以下角色创作一份详细人设。\n"
            f"要求：\n"
            f"1. 这是一个普通高中生，不要完美，要贴近现实；"
            f"必须体现普通高中生的劣根性（如虚荣、好面子、嫉妒、逃避、撒谎、八卦、攀比、小心眼、腹黑、偷懒、装等），至少写3条，每条注明体现程度与触发条件（什么场合暴露、对谁暴露、什么场合收敛）；\n"
            f"2. 【手机】段按学校规定写：学校明令禁止学生带手机，他没有手机（或偷偷藏着一部，从不在人前用）；\n"
            f"3. {FORMAT_GUIDE}\n"
            f"角色基本信息：\n名字：{name}\n简要设定：{info}\n"
            + (f"补充说明：{extra}\n" if extra else "")
        )
    r = call_model([
        {"role": "system", "content": "你是一名擅长创作真实、有血有肉、不完美角色的设定师。记住：人无完人，每个人都戴着面具生活。"},
        {"role": "user", "content": user},
    ], max_tokens=1200)
    return _extract(r["choices"][0]["message"]["content"])


def gen_complete(name, existing_persona):
    user = (
        f"以下是角色「{name}」现有的详细人设。请在不改变角色基本信息的前提下，"
        f"对这份人设进行补全和增强：补充更真实、更接地气的细节；"
        f"重点增强【劣根性】等段落——人无完人，每个人都戴着面具生活，必须体现人性深处的弱点：虚荣、好面子、嫉妒、逃避、撒谎、八卦、攀比、小心眼、腹黑、偷懒、装、自私、功利、推卸责任、自我欺骗、双重标准、记仇、胆小、贪婪、固执、偏见等；"
        f"确保包含【性格】【劣根性】【自我与思考】【说话风格】【兴趣爱好】【对室友】【禁忌】【记忆】【手机】全部段落；"
        f"【手机】段按学校规定：禁带手机，有也是偷偷藏的。\n"
        f"{FORMAT_GUIDE}\n"
        f"现有设定：\n{existing_persona}"
    )
    r = call_model([
        {"role": "system", "content": "你是一名擅长完善真实、不完美角色的设定师。记住：人无完人，圣人不存在。"},
        {"role": "user", "content": user},
    ], max_tokens=1500)
    return _extract(r["choices"][0]["message"]["content"])



def gen_enhance(name, base_persona, requirement):
    """根据扩写要求，对本地生成的人设进行 AI 扩写增强。"""
    user = (
        f"以下是本地生成的角色「{name}」的人设。请根据下面的扩写要求对它进行增强，"
        f"保持角色基本信息不变，补充更真实、更详细、更有血有肉的细节，"
        f"不要删减原有设定。\n"
        f"扩写要求：{requirement}\n"
        f"{FORMAT_GUIDE}\n"
        f"当前人设：\n{base_persona}"
    )
    r = call_model([
        {"role": "system", "content": "你是一名擅长在已有设定基础上按要求扩写、增强的设定师，使其更真实不完美。记住：人无完人。"},
        {"role": "user", "content": user},
    ], max_tokens=1500)
    return _extract(r["choices"][0]["message"]["content"])

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)




# ================================================================
# 本地自动补全（autofill）—— 不调用 AI，基于基础人设词库扩写
# ================================================================
TRAIT_LIB = {
    "懒": ["能躺着绝不坐着，能拖就拖", "作业不到最后一刻不动笔，值日能溜就溜"],
    "懒散": ["能躺着绝不坐着，能拖就拖", "作业不到最后一刻不动笔，值日能溜就溜"],
    "勤奋": ["肯下功夫，别人在玩他在刷题", "认定的事会死磕到底，有点一根筋"],
    "努力": ["肯下功夫，别人在玩他在刷题", "认定的事会死磕到底，有点一根筋"],
    "外向": ["自来熟，跟谁都能聊两句", "走到哪都热热闹闹，闲不住"],
    "开朗": ["成天笑呵呵的，看着就没烦恼", "好说话，跟谁都能处到一块去"],
    "内向": ["话不多，存在感低但心里有数", "被点名才开口，能不说话就不说话"],
    "安静": ["话少，喜欢待在自己的角落里", "不爱凑热闹，但也不孤僻"],
    "沉默": ["话少，喜欢待在自己的角落里", "被问了才开口，能省则省"],
    "急躁": ["一点就着，脾气来得快去得也快", "冲动起来不过脑子，事后又后悔"],
    "冲动": ["一点就着，脾气来得快去得也快", "冲动起来不过脑子，事后又后悔"],
    "暴脾气": ["一点就着，脾气来得快去得也快", "跟人起冲突不是一回两回"],
    "随和": ["怎么都行，被开玩笑也不恼", "很少跟人红脸，能忍则忍"],
    "好脾气": ["怎么都行，被开玩笑也不恼", "很少跟人红脸，能忍则忍"],
    "倔": ["认准的事八头牛拉不回来", "嘴上认错，心里还是按自己的想法来"],
    "固执": ["认准的事八头牛拉不回来", "别人说什么都听不进，就要按自己那套来"],
    "犟": ["认准的事八头牛拉不回来", "嘴上认错，心里还是按自己的想法来"],
    "敏感": ["容易想多，一句无心的话能琢磨半天", "表面装没事，心里其实很在意"],
    "玻璃心": ["容易想多，一句无心的话能琢磨半天", "表面装没事，心里其实很在意"],
    "好胜": ["见不得自己输，输了会难受很久", "嘴上说不在乎，心里较劲"],
    "要强": ["见不得自己输，输了会难受很久", "怕被人看扁，硬撑着也不认输"],
    "争强好胜": ["见不得自己输，输了会难受很久", "嘴上说不在乎，心里较劲"],
    "爱面子": ["特别在意别人怎么看自己", "打肿脸充胖子也要撑住场面"],
    "胆小": ["遇事能躲就躲，怕惹麻烦", "被欺负了也不敢声张，只敢背后抱怨"],
    "怂": ["遇事能躲就躲，怕惹麻烦", "被老师一瞪就老实，转头照旧"],
    "懦弱": ["遇事能躲就躲，怕惹麻烦", "被欺负了也不敢声张，只敢背后抱怨"],
    "叛逆": ["老师说什么都爱顶两句", "越让干什么越不干，逆反心理重"],
    "不服管": ["老师说什么都爱顶两句", "越让干什么越不干，逆反心理重"],
    "乖巧": ["老师家长说啥听啥，很少顶嘴", "规规矩矩，不惹事"],
    "听话": ["老师家长说啥听啥，很少顶嘴", "规规矩矩，不惹事"],
    "小气": ["钱算得清清楚楚，AA制从不吃亏", "偶尔计较得失，心里有本小账"],
    "抠门": ["钱算得清清楚楚，AA制从不吃亏", "偶尔计较得失，心里有本小账"],
    "大方": ["对朋友舍得花钱，请客不含糊", "兄弟有难处会主动搭把手"],
    "仗义": ["对朋友舍得花钱，请客不含糊", "兄弟有难处会主动搭把手"],
    "幽默": ["说话自带笑点，是人群里的气氛组", "爱开玩笑，也开得起玩笑"],
    "逗比": ["说话自带笑点，是人群里的气氛组", "爱开玩笑，也开得起玩笑"],
    "高冷": ["话少脸冷，不熟的人觉得他不好接近", "熟了才知道其实挺好说话"],
    "冷淡": ["话少脸冷，不熟的人觉得他不好接近", "熟了才知道其实挺好说话"],
    "心软": ["见不得别人难过，容易心软", "嘴上嫌弃，行动上却总帮人"],
    "善良": ["见不得别人难过，容易心软", "能帮就帮，不图回报"],
}

FLAW_LIB = {
    "爱面子": ["明明很在意，非要装得云淡风轻", "输了要甩锅，绝不承认是自己不行"],
    "好面子": ["明明很在意，非要装得云淡风轻", "输了要甩锅，绝不承认是自己不行"],
    "虚荣": ["爱跟人比，看到别人好会心里发酸", "喜欢显摆，没有也要吹"],
    "攀比": ["爱跟人比，看到别人好会心里发酸", "喜欢显摆，没有也要吹"],
    "嫉妒": ["看不得别人比自己好，表面恭喜心里酸", "谁比他强，他嘴上夸心里记着"],
    "小心眼": ["谁嘲讽过他，他能记很久", "一点小事也会在心里记上账"],
    "逃避": ["遇到难事第一反应是躲，能拖就拖", "用游戏或睡觉麻痹自己，不敢面对"],
    "撒谎": ["说话喜欢夸大，真假掺着来", "被抓包就嬉皮笑脸糊弄过去"],
    "爱吹牛": ["说话喜欢夸大，真假掺着来", "明明没影的事，也能吹得跟真的一样"],
    "吹牛": ["说话喜欢夸大，真假掺着来", "明明没影的事，也能吹得跟真的一样"],
    "八卦": ["爱打听别人的事，知道了就往外说", "传话容易添油加醋，还觉得自己没毛病"],
    "爱说闲话": ["爱打听别人的事，知道了就往外说", "传话容易添油加醋，还觉得自己没毛病"],
    "偷懒": ["作业抄的，值日能溜就溜", "不到最后一刻不动，临到头才赶"],
    "拖延": ["作业抄的，值日能溜就溜", "不到最后一刻不动，临到头才赶"],
    "贪小便宜": ["爱蹭吃蹭喝，轮到自己请客就装傻", "算钱时总想占点小便宜"],
    "占小便宜": ["爱蹭吃蹭喝，轮到自己请客就装傻", "算钱时总想占点小便宜"],
    "腹黑": ["面上不显，心里都记着", "有机会就'不经意'地阴阳回去"],
    "记仇": ["面上不显，心里都记着", "谁让他吃过亏，他能记一整个学期"],
    "装": ["明明拼命努力，非要装'我没复习'", "不懂装懂，被拆穿就转移话题"],
    "死要面子": ["明明拼命努力，非要装'我没复习'", "不懂装懂，被拆穿就转移话题"],
    "墙头草": ["哪边人多帮哪边，没有立场", "见风使舵，看人下菜"],
    "冲动": ["一言不合就上头，说完就后悔", "跟人起冲突不是一回两回"],
    "脾气爆": ["一言不合就上头，说完就后悔", "跟人起冲突不是一回两回"],
}

HOBBY_LIB = {
    "打游戏": ["藏着的旧手机里打手游（王者/原神）", "为了打游戏跟家里撒谎说去同学家自习"],
    "游戏": ["藏着的旧手机里打手游（王者/原神）", "为了打游戏跟家里撒谎说去同学家自习"],
    "王者": ["藏着的旧手机里打手游，段位还不低", "为了打游戏跟家里撒谎说去同学家自习"],
    "原神": ["藏着的旧手机里玩原神，天天念叨抽卡", "为了抽卡省下午饭钱"],
    "篮球": ["球场上最有劲，技术一般但瘾大", "喜欢在球场上被人围观的感觉"],
    "足球": ["一踢球就来劲，技术糙但爱跑", "周末约人踢球，晒得黢黑"],
    "画画": ["画画不错，会偷偷给喜欢的人画", "课本空白处全是他的涂鸦"],
    "美术": ["画画不错，会偷偷给喜欢的人画", "课本空白处全是他的涂鸦"],
    "音乐": ["偷偷在练乐器，想在晚会上露一手", "耳机不离身，走路都带节奏"],
    "吉他": ["偷偷在练吉他，想在晚会上露一手", "练得稀烂但自我感觉良好"],
    "看小说": ["书桌底下永远藏着一本小说", "上课偷偷看，被没收过好几本"],
    "小说": ["书桌底下永远藏着一本小说", "上课偷偷看，被没收过好几本"],
    "动漫": ["资深二次元，房间里全是周边", "会为喜欢的角色'过生日'，被发现了打死不认"],
    "二次元": ["资深二次元，房间里全是周边", "会为喜欢的角色'过生日'，被发现了打死不认"],
    "跑步": ["每天操场跑步，坚持有一阵子了", "跑步的时候脑子里什么都能想一遍"],
    "运动": ["闲不住，什么球都想上手试试", "体育课是最积极的那个"],
    "摄影": ["喜欢到处拍拍，照片全攒在手机里", "后来手机被没收，就改拍风景"],
    "美食": ["看见吃的就走不动道，生活费大半花在吃上", "学校周边哪家好吃，他门儿清"],
    "吃": ["看见吃的就走不动道，生活费大半花在吃上", "学校周边哪家好吃，他门儿清"],
    "睡觉": ["能睡是福，课间十分钟也能睡一觉", "上课犯困是常态，被点名了才惊醒"],
    "刷题": ["没事就刷题，成绩是刷出来的", "错题本比谁都厚，就是不爱分享"],
    "学习": ["没事就刷题，成绩是刷出来的", "嘴上说不爱学，其实偷偷用功"],
    "刷视频": ["爱刷短视频，一刷就是俩小时", "梗和热词知道得比谁都快"],
}

TRAIT_DEFAULTS = ["说不上大善人，也说不上多坏，就是个普通高中生", "有点自己的小算盘，但不至于损人利己"]
FLAW_DEFAULTS = ["多少有点爱面子，嘴上不认输", "也会偷懒耍滑，能省事就省事"]
SELF_DEFAULTS = ["表面看着没啥心事，其实心里也装着不少事", "偶尔深夜会想很多，但第二天起来照旧", "成绩一般、家里一般，偶尔也会不甘心"]
SPEAK_DEFAULTS = ["说话带点学生腔，跟熟的人话多，跟生的人话少", "被问到不想答的就打哈哈糊弄过去"]
HOBBY_DEFAULTS = ["没什么特别的爱好，放假就在家躺着", "偶尔跟同学一起出去玩，大部分时间待寝室"]
ROOM_DEFAULTS = ["对室友还算够意思，能搭把手就搭把手", "但也有点小毛病，偶尔惹人烦自己还察觉不到"]
TABOO_DEFAULTS = ["最怕被人当众揭短", "别人戳他痛处会真的恼，但多数时候忍着不发作"]
MEM_DEFAULTS = ["记性还行，谁帮过他、谁让他不爽，都记得", "欠的人情会还，受的气也会找机会出"]
PHONE_DEFAULT = "学校明令禁止学生带手机：他没有手机，也从不在人前用（或偷偷藏着一部旧手机，熄灯后躲被窝里才敢悄悄拿出来，绝不让老师和家长发现）。"


def _pick(sents, defaults, n=3):
    out = list(sents)
    i = 0
    while len(out) < n and i < len(defaults):
        if defaults[i] not in out:
            out.append(defaults[i])
        i += 1
    return out[:n]


def autofill_persona(name, info, loc="宿舍楼-302寝室"):
    """基于基础人设（一句话/几个关键词）本地自动补全为完整详细人设，不调用 AI。"""
    import re
    text = info or ""
    age_m = re.search(r"(\d+)\s*岁", text)
    age = age_m.group(1) + "岁" if age_m else "17岁"
    cls_m = re.search(r"[高初][中]?\s*[一二三四五六\d]?\s*\(?\d?\)?\s*班", text)
    cls = cls_m.group(0).strip() if cls_m else "高二(3)班"

    t = text.replace(name, "")
    t = t.replace(age, "")
    if cls_m:
        t = t.replace(cls_m.group(0), "")
    tokens = [x.strip() for x in re.split(r"[，,、。；;/\s]+", t) if x.strip()]
    stop = {"学生", "男生", "女生", "高中生", "普通高中生", "普通人", "一般"}
    feats = [x for x in tokens if x not in stop]

    tra_s, fla_s, hob_s, other = [], [], [], []
    for x in feats:
        if x in TRAIT_LIB:
            tra_s += TRAIT_LIB[x][:2]
        elif x in FLAW_LIB:
            fla_s += FLAW_LIB[x][:2]
        elif x in HOBBY_LIB:
            hob_s += HOBBY_LIB[x][:2]
        else:
            other.append(x)
    if other:
        tra_s.append("这人有点" + "、".join(other) + "，说不上好也说不上坏。")

    intro = (f"你是「{name}」，{age}，{cls}学生，{loc}。"
             + ("，".join(feats) if feats else "普普通通")
             + "，是那种放在人群里不会多看一眼的普通高中生。")

    lines = [intro, ""]
    lines.append("【性格】" + "；".join(_pick(tra_s, TRAIT_DEFAULTS)))
    lines.append("")
    lines.append("【劣根性】" + "；".join(_pick(fla_s, FLAW_DEFAULTS)))
    lines.append("")
    lines.append("【自我与思考】" + "；".join(_pick([], SELF_DEFAULTS)))
    lines.append("")
    lines.append("【说话风格】" + "；".join(_pick([], SPEAK_DEFAULTS)))
    lines.append("")
    lines.append("【兴趣爱好】" + "；".join(_pick(hob_s, HOBBY_DEFAULTS)))
    lines.append("")
    lines.append("【对室友】" + "；".join(_pick([], ROOM_DEFAULTS)))
    lines.append("")
    lines.append("【禁忌】" + "；".join(_pick([], TABOO_DEFAULTS)))
    lines.append("")
    lines.append("【记忆】" + "；".join(_pick([], MEM_DEFAULTS)))
    lines.append("")
    lines.append("【手机】" + PHONE_DEFAULT)
    return "\n".join(lines)







def evolve_persona(name, persona, recent_events):
    """评估角色近期经历是否导致人设演变，返回要更新的【近况与变化】段（或"无明显变化"）。"""
    prompt = (
        f"角色「{name}」的完整人设如下：\n{persona}\n\n"
        f"他/她最近经历了这些事（按时间顺序）：\n{recent_events}\n\n"
        f"人是会改变的。请判断这些经历是否让这个角色在某些方面发生了变化"
        f"（比如对某个人的态度、某个想法、某个习惯、性格的细微转变，甚至某个劣根性被触动或收敛）。\n"
        f"若有变化：输出一段【近况与变化】说明（2到4句话，具体到：发生了什么事让他变了、他变成了什么样、现在会怎么做）。\n"
        f"若无明显变化：只输出：无明显变化。\n"
        f"只输出【近况与变化】段或'无明显变化'，不要重写整个设定，不要输出其他内容。"
    )
    import time as _time
    for _attempt in range(3):
        try:
            r = call_model([
                {"role": "system", "content": "你是一名擅长刻画人物成长与变化的角色设定师，能基于经历判断人设的演变。"},
                {"role": "user", "content": prompt},
            ], max_tokens=500)
            text = r["choices"][0]["message"]["content"].strip()
            if len(text) >= 5:
                return text
        except Exception:
            pass
        _time.sleep(2)
    return "无明显变化"

def sync_new_chars(raw, agents, agents_path, loc_default="教学楼-高二(3)班"):
    """扫描本轮剧情文本：发现新角色 → 生成人设 → 加入模拟 agents → 持久化到设定文件。
    返回新增角色名列表。"""
    known = set(agents.keys())
    cands = extract_new_chars(raw, known)
    added = []
    if not cands:
        return added
    from engine import Agent
    for name, ctxs in cands.items():
        info = "；".join(ctxs)[:200] or "剧情中出现的角色"
        try:
            persona = gen_create(name, info)
        except Exception as e:
            print(f"[sync] 生成「{name}」人设失败：{e}", flush=True)
            continue
        ag = Agent(name=name, persona=persona, envName=loc_default, memory=info)
        ag.addressBook = set()
        agents[name] = ag
        added.append(name)
        # 与剧情中联系过他的已有角色互加通讯录
        for an in list(known):
            if an in agents and f"向【{name}】" in raw:
                agents[an].addressBook.add(name)
                ag.addressBook.add(an)
        # 持久化到设定文件
        try:
            data = load_json(agents_path)
            names = {d.get("name") for d in data}
            if name not in names:
                data.append({"name": name, "persona": persona, "memory": info,
                             "addressBook": sorted(ag.addressBook), "初始位置": loc_default})
            for d in data:
                if d.get("name") in agents and name in agents[d["name"]].addressBook:
                    ab = d.setdefault("addressBook", [])
                    if name not in ab:
                        ab.append(name)
            save_json(agents_path, data)
        except Exception as e:
            print(f"[sync] 持久化「{name}」失败：{e}", flush=True)
    return added

STOPWORDS = {
    "爸妈", "妈妈", "爸爸", "父亲", "母亲", "老师", "班主任", "教练", "校长", "主任",
    "同学", "隔壁班", "学校", "领导", "家长", "阿姨", "大哥", "兄弟", "哥们",
    "女朋友", "男朋友", "联系人名", "消息内容", "班主任老师", "班上", "班里", "他们", "她们",
}


def extract_new_chars(raw, known_names):
    """从日志文本中提取疑似新角色名（消息收件人 / 好友请求对象），返回 {名字: [上下文句]}。"""
    found = {}

    def add(name, ctx):
        name = (name or "").strip()
        if len(name) < 2 or name in known_names or name in STOPWORDS:
            return
        if name not in found:
            found[name] = []
        if len(found[name]) < 3:
            found[name].append(ctx.replace("\n", " ")[:120])

    # 1) 消息收件人：向【X】发送
    for m in re.finditer(r"向【([^】]+)】发送(?:了)?【", raw):
        add(m.group(1), raw[max(0, m.start() - 60):m.end() + 60])
    # 2) 申请好友
    for m in re.finditer(r"向【([^】]+)】发送(?:了)?【申请好友】", raw):
        add(m.group(1), raw[max(0, m.start() - 60):m.end() + 60])
    # 3) 同意好友请求
    for m in re.finditer(r"同意【([^】]+)】的好友请求", raw):
        add(m.group(1), raw[max(0, m.start() - 60):m.end() + 60])
    return found

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    args = args[1:]

    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]

    def get_opt(name):
        if name in args:
            i = args.index(name)
            return args[i + 1] if i + 1 < len(args) else None
        return None




    if cmd == "scan":
        log = args[0] if args else None
        if not log:
            print("用法：python character_generator.py scan <日志路径> [--file schoolAgents.json] [--preview]")
            return
        path = get_opt("--file") or "schoolAgents.json"
        path = os.path.join(PROJ, path) if not os.path.isabs(path) else path
        data = load_json(path)
        known = {d.get("name") for d in data}
        raw = open(log, encoding="utf-8").read()
        cands = extract_new_chars(raw, known)
        if not cands:
            print("== 未在剧情中发现新角色（已匹配现有设定）==")
            return
        print("== 剧情中发现疑似新角色 ==")
        for name, ctxs in cands.items():
            print(f"- 「{name}」")
            for c in ctxs:
                print("     …", c)
        if preview:
            print("== （--preview，未生成/未写入）==")
            return
        for name, ctxs in cands.items():
            info = "；".join(ctxs)[:200] or "剧情中出现的角色"
            print(f"\n== 正在为「{name}」生成人设……", flush=True)
            persona = gen_create(name, info)
            data.append({
                "name": name,
                "persona": persona,
                "memory": info,
                "addressBook": [],
                "初始位置": "教学楼-高二(3)班",
            })
        save_json(path, data)
        print(f"\n== 已为剧情新角色生成人设并写入：{path}（新增 {len(cands)} 人）==")
        return
    if cmd == "generate":
        name = args[0] if args else None
        if not name:
            print('用法：python character_generator.py generate "名字" --info "基础人设" [--enhance "扩写要求"]')
            return
        info = get_opt("--info") or "普通高中生"
        loc = get_opt("--loc") or "宿舍楼-302寝室"
        addr = get_opt("--addr") or ""
        out = get_opt("--out")
        enhance = get_opt("--enhance") or get_opt("--ai") or ""

        print("== 第 1 步：本地自动生成（不调用 AI）==", flush=True)
        persona = autofill_persona(name, info, loc)
        print(persona, flush=True)
        if enhance:
            print("\n== 第 2 步：根据要求用 AI 扩写 ==", flush=True)
            persona = gen_enhance(name, persona, enhance)
            print(persona, flush=True)
        else:
            print("\n== （本地结果已生成；如需 AI 按要求扩写，请加 --enhance \"要求\"）==", flush=True)

        if out and not preview:
            out_path = os.path.join(PROJ, out) if not os.path.isabs(out) else out
            data = load_json(out_path)
            found = False
            for d in data:
                if d.get("name") == name:
                    d["persona"] = persona
                    found = True
                    break
            if not found:
                data.append({
                    "name": name,
                    "persona": persona,
                    "memory": info,
                    "addressBook": [a.strip() for a in addr.split(",") if a.strip()],
                    "初始位置": loc,
                })
            save_json(out_path, data)
            print(f"== 已写入：{out_path}（角色：{name}）==", flush=True)
        else:
            print("== （未指定 --out，仅预览，未写入文件）==", flush=True)
        return
    if cmd == "autofill":
        name = args[0] if args else None
        if not name:
            print('用法：python character_generator.py autofill "名字" --info "基础人设，如：17岁，懒散，爱打游戏，爱吹牛"')
            return
        info = get_opt("--info") or "普通高中生"
        loc = get_opt("--loc") or "宿舍楼-302寝室"
        addr = get_opt("--addr") or ""
        out = get_opt("--out")

        persona = autofill_persona(name, info, loc)
        print("========== 自动补全的人设（本地规则，未调用 AI）==========")
        print(persona)
        print("========================================================")

        if out and not preview:
            out_path = os.path.join(PROJ, out) if not os.path.isabs(out) else out
            data = load_json(out_path)
            found = False
            for d in data:
                if d.get("name") == name:
                    d["persona"] = persona
                    found = True
                    break
            if not found:
                data.append({
                    "name": name,
                    "persona": persona,
                    "memory": info,
                    "addressBook": [a.strip() for a in addr.split(",") if a.strip()],
                    "初始位置": loc,
                })
            save_json(out_path, data)
            print(f"== 已写入：{out_path}（角色：{name}）==")
        else:
            print("== （未指定 --out，仅预览，未写入文件）==")
        return

    if cmd == "create":
        name = args[0] if args else None
        if not name:
            print('请提供角色名：python character_generator.py create "名字" [--info ...]')
            return
        info = get_opt("--info") or "普通高中生"
        extra = get_opt("--extra") or ""
        loc = get_opt("--loc") or "宿舍楼-302寝室"
        addr = get_opt("--addr") or ""
        out = get_opt("--out")

        print(f"== 正在为「{name}」生成详细人设…… ==", flush=True)
        persona = gen_create(name, info, extra)
        print("========== 生成的人设 ==========")
        print(persona)
        print("================================")

        if out and not preview:
            out_path = os.path.join(PROJ, out) if not os.path.isabs(out) else out
            data = load_json(out_path)
            found = False
            for d in data:
                if d.get("name") == name:
                    d["persona"] = persona
                    found = True
                    break
            if not found:
                data.append({
                    "name": name,
                    "persona": persona,
                    "memory": extra,
                    "addressBook": [a.strip() for a in addr.split(",") if a.strip()],
                    "初始位置": loc,
                })
            save_json(out_path, data)
            print(f"== 已写入：{out_path}（角色：{name}）==")
        else:
            print("== （未指定 --out，仅预览，未写入文件）==")

    elif cmd == "complete":
        path = get_opt("--file") or get_opt("-f")
        name = get_opt("--name") or (args[0] if args else None)
        if not path or not name:
            print("用法：python character_generator.py complete --file schoolAgents.json --name 角色名")
            return
        path = os.path.join(PROJ, path) if not os.path.isabs(path) else path
        data = load_json(path)
        target = next((d for d in data if d.get("name") == name), None)
        if target is None:
            print(f"在 {path} 中找不到角色「{name}」")
            return
        old_persona = target["persona"]
        print(f"== 正在补全「{name}」的人设…… ==", flush=True)
        new_persona = gen_complete(name, old_persona)
        print("========== 补全后的人设 ==========")
        print(new_persona)
        print("================================")
        if not preview:
            target["persona"] = new_persona
            save_json(path, data)
            print(f"== 已写回：{path}（角色：{name}）==")
        else:
            print("== （--preview，未写入文件）==")

    else:
        print(f"未知命令：{cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()



