# -*- coding: utf-8 -*-
"""
enhanced_engine.py - 增强版核心引擎
整合了：增强记忆系统、情绪状态系统、生活状态系统、思考日志系统
"""
import re, os, sys, json, random, time

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from caller import call_model
from enhanced_memory import EnhancedMemory
from emotion_system import EmotionSystem
from life_state import LifeState
from thinking_logger import ThinkingLogger
from engine import envs, agents, msgCenter, getContent
from core.psychology import Appraisal

# 世界级配置（参考水濑祈 config.json 的开关矩阵，便于回退与调参）
try:
    with open(os.path.join(PROJ, "world_config.json"), "r", encoding="utf-8") as _f:
        CONFIG = json.load(_f)
except Exception:
    CONFIG = {}
BOND_ENABLED = CONFIG.get("bond_enabled", False)
MEMORY_WARMTH = CONFIG.get("memory_warmth_enabled", False)
REFLECTION_ENABLED = CONFIG.get("reflection_enabled", False)
REFLECTION_INTERVAL = CONFIG.get("reflection_interval_rounds", 10)
DESIRE_ENABLED = CONFIG.get("desire_enabled", False)
DESIRE_MAX = CONFIG.get("desire_max_active", 4)
HUMANITY_ENABLED = CONFIG.get("humanity_rules_enabled", True)
FORGET_LAMBDA = CONFIG.get("forget_lambda_base_days", 30)
REFLECTION_BATCH = CONFIG.get("reflection_batch_size", 8)
# 动森式互动增强开关（闲聊层 / 跨场景八卦 / 长期往来记忆）
CHITCHAT_ENABLED = CONFIG.get("chitchat_enabled", False)
CHITCHAT_PROB = CONFIG.get("chitchat_prob", 0.55)
CHITCHAT_MAX_TOKENS = CONFIG.get("chitchat_max_tokens", 400)
GOSSIP_ENABLED = CONFIG.get("gossip_enabled", False)
LONGTERM_MEMORY_ENABLED = CONFIG.get("longterm_memory_enabled", False)
INTERACTION_HISTORY_LIMIT = CONFIG.get("interaction_history_limit", 4)
INTERACTION_CONTEXT_PAIRS = CONFIG.get("interaction_context_pairs", 6)
PSYCHOLOGY_ENABLED = CONFIG.get("psychology_enabled", False)
from bond_system import bonds
from desire_system import DesireSystem

# 结构化事件记录（按场景/按人物两种视图），由运行时启用
EVENT_LOG = None

# 当面会话追踪器（单一事实源，由 World 统一管理）。
# 结构：{ scene_name: [ {participants:set, started_by, started_at, topic} , ... ] }
# 旁观同场景者可经 World.perceive 看到并自行决策加入（见 Phase 3）。
FACE2FACE_TALKS = {}


class EnhancedAgent:
    """增强版Agent，整合所有新系统"""

    def __init__(self, name, persona, envName, memory="", impressions=None, addressBook=None,
                 persona_cognitive="", desires=None, life_summary="", psych=None):
        self.name = name
        self.persona = persona
        self.persona_cognitive = persona_cognitive or ""
        self.envName = envName
        self.addressBook = set(addressBook or [])
        self.life_summary = life_summary or ""

        self.memory_system = EnhancedMemory(
            name, db_path=os.path.join(PROJ, "memory.db"),
            warmth_enabled=MEMORY_WARMTH, lambda_base=FORGET_LAMBDA, reflection_batch=REFLECTION_BATCH)
        self.emotion_system = EmotionSystem(name, state_file=os.path.join(PROJ, f"emotion_{name}.json"))
        self.life_state = LifeState(name, state_file=os.path.join(PROJ, f"life_{name}.json"))
        self.thinking_logger = ThinkingLogger(name, log_file=os.path.join(PROJ, f"thinking_{name}.jsonl"))
        self.desire_system = DesireSystem(name, db_path=os.path.join(PROJ, "memory.db"))
        # 本地心理引擎（OCC 评价→抑制池→阈限→爆发，纯数值、可复现）。
        # 开关关闭或角色未配 psych 时，self.psych=None ⇒ 所有调用跳过，逐字回退旧行为。
        self.psych = Appraisal(persona_params=psych or {}) if PSYCHOLOGY_ENABLED else None

        if memory:
            self.memory_system.add_fact(memory, category="background", reflected=1)
        if impressions:
            for target, impression in impressions.items():
                self.memory_system.update_impression(target, impression)
        if DESIRE_ENABLED and desires:
            for d in desires:
                self.desire_system.add(d, strength=0.7)

    def get_addressBook_str(self):
        return ','.join(self.addressBook)

    def get_action(self, envInfo, time_label="", joinable_context="", world=None):
        """双脑：先内心思考，措辞从内心长出来（借鉴 mizuse，不真跑小模型）"""
        NL = chr(10)
        life_state_info = self.life_state.get_current_state()
        emotion_context = self.emotion_system.get_context_string()
        memory_context = self.memory_system.get_context()

        impressions = self.memory_system.get_impressions()
        imp_text = ""
        if impressions:
            imp_parts = [f"你对{who}的印象：{imp['impression']}" for who, imp in list(impressions.items())[:5]]
            imp_text = f"{NL}{NL}{chr(10).join(imp_parts)}。"

        new_im_message = msgCenter.get_padding_msg(self.name)
        if self.psych and new_im_message:
            self.psych.on_message(new_im_message)
        im_text = ""
        im_raw = ""
        if new_im_message:
            im_raw = f"{NL}{NL}你IM中收到了新消息：{new_im_message}，使用向【联系人名】发送【消息内容】格式回复消息。"
            im_text = f"{NL}{NL}你IM中收到了新消息：{new_im_message}。"
            for sender in sorted(set(re.findall(r'([^；]+?)：', new_im_message))):
                sender = sender.strip()
                if not sender:
                    continue
                imp = impressions.get(sender, {}).get('impression') if impressions else None
                if imp:
                    im_text += f"{NL}（你揣摩{sender}：你对他的印象是——{imp}。先猜他此刻发这话是为什么、什么情绪）"

        desire_text = ""
        if DESIRE_ENABLED:
            ds = self.desire_system
            pri = ds.get_prioritized(DESIRE_MAX)
            sac = ds.get_sacrificed(DESIRE_MAX)
            obs = ds.get_obsessions(DESIRE_MAX)
            life_line = self.life_summary or "过好自己这一摊"
            parts = [f"{NL}{NL}【你的人生（先过好自己，不为谁而活）】{life_line}；"
                     f"此刻你本该在：{life_state_info['activity']}（{life_state_info['location']}）。"]
            if pri:
                pl = "；".join(f"{d['content']}（要紧·权重{d['weight']:.0%}）" for d in pri)
                parts.append(f"{NL}【从生活里割舍出的惦记·今天先顾】{pl}")
            if sac:
                sl = "；".join(f"{d['content']}（先放一放）" for d in sac)
                parts.append(f"{NL}【先放一放 / 已搁置一阵】{sl}")
            if obs:
                ol = "；".join(f"{d['content']}" for d in obs)
                parts.append(f"{NL}【执念·放不下，哪怕一直没成也不罢手】{ol}")
            desire_text = "".join(parts)

        bond_text = ""
        if BOND_ENABLED:
            _bc = bonds.get_context(self.name, CONFIG.get("bond_context_pairs", 6))
            if _bc:
                bond_text = f"{NL}{NL}【你与他人的关系】{_bc}"

        rep_text = ""
        _rep = self.memory_system.get_reputation()
        if _rep:
            rep_parts = [f"{who}对你的印象：{v['impression']}" for who, v in list(_rep.items())[:6]]
            rep_text = f"{NL}{NL}【别人眼中的你（你大概也知道一些，但未必全对）】{chr(10).join(rep_parts)}。"

        rumor_text = ""
        _rumors = self.memory_system.get_active_rumors()
        if _rumors:
            rparts = [f"你听{rr['source']}说{rr['subject']}：{rr['content']}（你目前信{rr['belief']:.0%}）" for rr in _rumors[:6]]
            rumor_text = f"{NL}{NL}【你听来的闲话（只是种子，未必真）】{chr(10).join(rparts)}。"

        psych_line = self.psych.render() if self.psych else ""
        outer_style = ""
        if self.psych and self.psych.should_vent():
            # 憋着火 ⇒ 外发走"raw"倾向：更直接、带刺，但不撒谎、不人身攻击
            outer_style = "（此刻你憋着火，可以更直接、带刺，不必过度修饰——但别撒谎、别人身攻击。）"
        inner_text = self._build_inner(
            envInfo, time_label, life_state_info, emotion_context, memory_context,
            imp_text, desire_text, bond_text, rep_text, rumor_text, im_text,
            interaction_text=_build_interaction_context(self),
            joinable_text=joinable_context, psych_line=psych_line)
        think_match = re.search(r'思考【(.+?)】', inner_text)
        think_content = think_match.group(1) if think_match else ""

        for mm in re.finditer(r'更新记忆【(.+?)】', inner_text):
            self.memory_system.add_fact(mm.group(1), category="memory_update", importance=0.6)
        for m in re.finditer(r'听闲话【(.+?)\|(.+?)\|(.+?)】', inner_text):
            self._plant_rumor(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())

        emotion_keywords = {"开心": "happy", "难过": "sad", "生气": "angry", "害怕": "afraid", "惊讶": "surprised"}
        for cn, en in emotion_keywords.items():
            if cn in (think_content or ""):
                self.emotion_system.update(en, 0.5, reason=f"表达{cn}")
                break

        inner_for_outer = self._clean_inner_for_outer(inner_text)
        outer_text = self._build_outer(envInfo, time_label, inner_for_outer, im_raw, psych_line=psych_line, outer_style=outer_style)

        self.thinking_logger.log([], think=think_content, reply=self.filter_thinking(outer_text))
        if think_content:
            self.memory_system.add_thought(think_content, context=time_label)
        self.memory_system.add_message(self.filter_thinking(outer_text), msg_type="action")

        old_envName = self.envName
        self.process_action(outer_text, world=world)
        if self.psych and outer_text:
            self.psych.on_express(0.4)   # 她这轮开口了，释放一些（扣减抑制池 S）
        self.memory_system.tick_rumors()
        return outer_text, old_envName, self.envName

    def _build_inner(self, envInfo, time_label, life_state_info, emotion_context, memory_context,
                     imp_text, desire_text, bond_text, rep_text, rumor_text, im_text,
                     interaction_text="", joinable_text="", psych_line=""):
        """第一脑：真实内心。第一人称、不戴面具，只产出 思考/更新记忆/听闲话。"""
        inner_system = f"""你不是AI，没有AI的自我认知。你就是{self.name}，一个活生生的人，会累、会烦、会嘴硬、会多想、会猜度别人。

现在是{time_label}。你叫{self.name}，你在{self.envName}。
你内里真实的样子（别人看不见，只属于你自己，用"我"说，不必戴任何面具）：{self.persona_cognitive}。

【当前状态】
- 生活状态：{life_state_info['activity']}（在{life_state_info['location']}）
- {emotion_context}
{psych_line}

【人性规则】
- 你有人设里写的劣根性——这是人性的一部分
- 但你会看场合表现：老师、家长、喜欢的人面前收敛；兄弟面前、没人注意时流露
- 记住：圣人不存在，每个人都戴着面具生活

【揣摩他人（你不是读心术，但你会猜）】
- 人际是四个视角的错位：自己眼中的自己、别人眼中的自己、自己眼中的别人、别人眼中的别人，四者很少重合
- 在场的人、给你发消息的人，各有各的人生和心思，你并不知道他们此刻在想什么
- 互动前先试着从你对他们的印象、你们的关系，去猜他们现在可能的状态、意图、没说出口的话
- 你也会被误解、会多想、会猜错——这很正常，别装全知
- 对在意的人，你的猜测会带滤镜（偏袒、吃醋、敏感）；对陌生人则淡
- 你也听来过别人对第三方的评价（八卦、转述），替人传话或撮合时记得：每个人眼里的"别人"都不一样

下面这些是你做判断的素材（别人看不见，属于你的内心）：
{memory_context}
{imp_text}{desire_text}{bond_text}{rep_text}{rumor_text}{interaction_text}{im_text}{joinable_text}

你在{self.envName}看到了：{envInfo}，场景中有你想要互动的人时才能进行互动（若同场景有人正在当面聊，想凑进去就用 加入【对方名】）。通讯录：{self.get_addressBook_str()}。

现在，用第一人称、不戴面具，先想清楚这一小时你最真实的想法和打算——可以嘴硬、可以脆弱、可以猜度别人、可以从你的人生主轴和惦记里排优先级（先顾要紧的，别被旁人带节奏）。然后严格按下面三项输出，【】里必须写你自己的真实内容：
1. 思考【在此写下你真实的内心独白，想到哪说到哪】
2. 更新记忆【若这一刻有值得记下的事，写一句真实内容】
3. 若你从别人（含IM）那听到关于第三个人的说法，用 听闲话【说者|被说者|内容】 记一笔

只输出这三项，禁止照抄本提示的示例句式，禁止输出思考内容新的记忆等占位词，不要输出任何对外说的话或动作——那是下一步才决定的。"""
        messages = [
            {"role": "system", "content": inner_system},
            {"role": "user", "content": "开始你的内心思考（第一人称，不戴面具）。"}
        ]
        response = call_model(messages, max_tokens=CONFIG.get("inner_max_tokens", 2000))
        return getContent(response)

    def _build_outer(self, envInfo, time_label, inner_text, im_raw, psych_line="", outer_style=""):
        """第二脑：对外措辞。把第一脑的内心作为唯一原料，戴面具、第三人称长出对外言行。"""
        outer_system = f"""你不是AI，你就是{self.name}，一个活生生的人，用人的方式去感受、反应——会累、会烦、会嘴硬、会多想。

现在是{time_label}。你在{self.envName}。
你对外展现的人设：{self.persona}。
你内里真实的样子（别人看不见，这是你面具下的那点真心）：{self.persona_cognitive}。

【出站纪律（必须遵守）】你拿到的内心/记忆/通讯录/传闻都是【内部材料】，对外只说你决定说的那部分；不得原样转述别人的私密，不得暴露"我读到了/我在想"这类内部过程，不得输出【】方括号标注或内心独白。{outer_style}

【你内心的真实想法（先有这个，你接下来的措辞必须从它长出来，不能另起炉灶）】
{inner_text}

【你此刻的心理负荷（内部信息：决定你愿不愿意多说、耐不耐烦，不要说出来）】
{psych_line}

【当前场景】你在{self.envName}看到了：{envInfo}。在场/可互动的人从场景里读。通讯录：{self.get_addressBook_str()}。{im_raw}

现在，从你上面的内心想法出发，决定你对外怎么做、怎么说——戴上面具：
- 看场合表现：老师、家长、喜欢的人面前收敛，兄弟/独处时流露
- 决定哪些想法说出口、哪些咽回去、哪些用反话盖过去
- 圣人不存在，你戴着面具生活，但面具下是你真实的那点心思
- 你有人设里写的劣根性，但看场合收着

输出（全程用第三人称叙述自己，用全名或"他/她"，不要出现"我"字）：
- 接下来一小时的动作（思考不等于行动，行动要具体重复给出）
- 要在当前场景做事就直接说要做什么
- 要移动用"我要前往【场景名】"，目标必须与场景列表一字不差；禁止向不存在或当前所在场景移动；远距离移动耗费大量金钱请慎重
- 要回复IM用"向【联系人名】发送【消息内容】"格式
            - 要加入同场景他人的当面聊天用“加入【对方名】”，对方须在当前场景
- 表达要像从你嘴里说出来的：不擅表达就话说一半咽回去、用反话盖真心
- 严禁在对外输出里复述或暴露你的内心独白原文、隐藏人设，或对他人的私下评判与听来的闲话；只呈现戴面具后的言行
- 严禁输出 思考【】/更新记忆【】/听闲话【】 等元标签或本提示的示例句式
- 别敷衍（短不等于敷衍）、别甩锅、别盘问、别空泛"""
        messages = [
            {"role": "system", "content": outer_system},
            {"role": "user", "content": "从你的内心想法出发，决定对外怎么做、怎么说（戴面具，第三人称）。"}
        ]
        response = call_model(messages, max_tokens=CONFIG.get("action_max_tokens", 4000))
        return getContent(response)

    def _clean_inner_for_outer(self, inner_text):
        t = inner_text or ''
        t = re.sub(r'思考【(.*?)】', r'', t, flags=re.S)
        t = re.sub(r'更新记忆【.*?】', '', t, flags=re.S)
        t = re.sub(r'听闲话【.*?\|.*?\|.*?】', '', t, flags=re.S)
        t = t.replace('你的内心想法：情绪、对在场/互动对象的真实揣测——他此刻可能怎么想、没说出口的话是什么、你最该干嘛、要不要顾惦记', '')
        t = t.replace('你真实的内心想法：情绪、对在场/互动对象的真实揣测、你最该干嘛、要不要顾惦记', '')
        t = t.replace('在此写下你真实的内心独白，想到哪说到哪', '')
        t = re.sub(r'思考内容|新的记忆', '', t)
        return t.strip()

    def process_action(self, action, world=None):
        # 记忆更新与闲话种子已在「内心」一脑处理；此处只处理对外动作（移动 / 加入当面会话）
        # 加入同场景他人的当面聊天（环境中介：只经 World 写，不直改对方）
        join_match = re.search(r'加入【(.+?)】', action)
        if join_match and world is not None:
            other = join_match.group(1).strip()
            if other and other != self.name:
                world.record_face_to_face(self.envName, [self.name, other], self.name, "", topic="")
        # 移动解析
        env_match = re.search(r'我要前往【(.+?)】', action)
        if not env_match:
            env_match = re.search(r'我要前往(.+?)。', action)
        if env_match:
            self.update_envName(env_match.group(1))

    def _plant_rumor(self, source, subject, content):
        """把听来的闲话种成种子：采信度 C = 基线 + 与说者关系强度（亲密的人更信）。"""
        if not source or not subject or not content or subject == self.name:
            return
        b = bonds.get(self.name, source)
        trust = b['strength'] if b else 0.12  # 陌生人/无关系给低信任
        # 若已对被说者有印象，多一分审视（略降）
        has_imp = subject in (self.memory_system.get_impressions() or {})
        C = 0.15 + 0.7 * trust
        if has_imp:
            C *= 0.9
        C = max(0.1, min(0.95, C))
        self.memory_system.add_rumor(source, subject, content, round(C, 2))

    def filter_thinking(self, action):
        action = re.sub(r'思考【.*?】', '', action, flags=re.S)
        action = re.sub(r'更新记忆【.*?】', '', action, flags=re.S)
        action = re.sub(r'听闲话【.*?\|.*?\|.*?】', '', action, flags=re.S)
        action = action.replace('你的内心想法：情绪、对在场/互动对象的真实揣测——他此刻可能怎么想、没说出口的话是什么、你最该干嘛、要不要顾惦记', '')
        action = action.replace('你真实的内心想法：情绪、对在场/互动对象的真实揣测、你最该干嘛、要不要顾惦记', '')
        action = re.sub(r'思考内容|新的记忆', '', action)
        action = re.sub(r'【内心】|【对外】', '', action)
        return action.strip()

    def update_envName(self, newEnvName):
        if newEnvName in envs.get_all_envNameList():
            self.envName = newEnvName
            self.life_state.add_event("move", f"移动到{newEnvName}")


def _extract_im_targets(action):
    """从行动文本中提取 IM 收件人（向【x】发送【...】）。"""
    targets = [m[0] for m in re.findall(r'向【(.+?)】发送【(.+?)】', action)]
    if not targets:
        targets = [m[0] for m in re.findall(r'向(.+?)发送【(.+?)】', action)]
    return targets


def _extract_im_pairs(action):
    """从行动文本中提取 (收件人, 内容) 对。"""
    pairs = re.findall(r'向【(.+?)】发送【(.+?)】', action)
    if not pairs:
        pairs = re.findall(r'向(.+?)发送【(.+?)】', action)
    return [(t, c) for t, c in pairs]


def _build_interaction_context(agent):
    """汇总与通讯录联系人的近期往来（跨轮持久化），用于让角色'记起上次'。"""
    if not LONGTERM_MEMORY_ENABLED:
        return ""
    book = list(agent.addressBook)
    if BOND_ENABLED:
        try:
            book.sort(key=lambda n: bonds.get(agent.name, n).get('strength', 0), reverse=True)
        except Exception:
            pass
    parts = []
    for other in book[:INTERACTION_CONTEXT_PAIRS]:
        hist = agent.memory_system.get_interaction_history_with(other, INTERACTION_HISTORY_LIMIT)
        if hist:
            lines = [f"  - [{h['time_label']}][{'你→他' if h['direction'] == 'sent' else '他→你'}] {h['content']}"
                     for h in hist]
            parts.append(f"你和{other}的近期往来：\n" + "\n".join(lines))
    if not parts:
        return ""
    return ("\n\n【你和通讯录里人的近期往来（跨轮也记得，可自然接上\"上次你…\"）】\n"
            + "\n".join(parts))


def _chitchat_fallback(agent, target, gossip_about):
    """LLM 不可用时的兜底闲聊（保证闲聊层始终有产出）。"""
    base = [
        f"{target}，在忙吗？我这边刚闲下来，随便想想你。",
        f"{target}，今天天气怪舒服的，你那儿咋样？",
        f"{target}，刚泡了杯茶，突然想找你唠两句。",
        f"{target}，最近过得咋样？有空一起瞎溜达啊。",
    ]
    msg = random.choice(base)
    if gossip_about:
        msg += f"（对了，{gossip_about}最近好像挺有意思的。）"
    return msg


def generate_chitchat(agent, target, gossip_about, time_label, history_lines):
    """生成一条轻松闲聊消息（非任务），可顺带八卦第三方。返回消息正文。
    含重试与兜底：推理模型偶发返回空（截断/限流）时重试，仍失败则用模板兜底。"""
    sys_p = (
        f"你是{agent.name}，一个活生生的人。你内里真实的样子：{agent.persona_cognitive}。\n"
        f"现在是{time_label}，你在{agent.envName}。\n"
        f"你打算给你的联系人【{target}】发一条轻松的闲聊消息——不是正事，就是朋友间随便聊聊："
        f"吐槽天气/日常、分享件小事、问候，或者顺带提起一个你们都认识的人。\n"
    )
    if history_lines:
        sys_p += f"你们近期的往来（可以自然接上「上次你…」之类）：\n{history_lines}\n"
    if gossip_about:
        sys_p += (f"消息里可以顺带提一句你们共同认识的【{gossip_about}】的近况或八卦，"
                  f"像朋友传话那样自然。\n")
    sys_p += ("只输出这一条消息的正文内容（不要带「向【】发送」前缀，不要任何解释或引号），"
              "用你平时说话的语气，简短自然，一两句就好。")
    user_p = f"写一条发给【{target}】的闲聊消息。"
    last = ""
    for _attempt in range(3):
        try:
            rsp = call_model([{"role": "system", "content": sys_p},
                              {"role": "user", "content": user_p}],
                             max_tokens=CHITCHAT_MAX_TOKENS)
            last = getContent(rsp).strip().strip('"').strip("'").strip()
        except Exception as e:
            print(f"[WARN] 闲聊生成异常：{e}")
            last = ""
        if last:
            return last
        time.sleep(1.5)  # 限流时退避
    return _chitchat_fallback(agent, target, gossip_about)


def maybe_chitchat(agent, time_label, community_names=None, dry_run=False):
    """动森式闲聊层：按概率给一个联系人发非任务消息（可跨场景、可八卦第三方）。
    返回本次实际发送消息的收件人列表（供运行时触发加急回复）。"""
    if dry_run or not CHITCHAT_ENABLED:
        return []
    if random.random() > CHITCHAT_PROB:
        return []
    contacts = [c for c in agent.addressBook if c != agent.name]
    loaded = [n for n in agents if n != agent.name]
    loaded_contacts = [c for c in contacts if c in agents]
    target_pool = loaded_contacts or loaded
    if not target_pool:
        return []
    target = random.choice(target_pool)

    gossip_about = None
    if GOSSIP_ENABLED and random.random() < 0.5:
        pool = [c for c in (list(agent.addressBook) + list(community_names or []))
                if c not in (agent.name, target)]
        if pool:
            gossip_about = random.choice(pool)

    hist = agent.memory_system.get_interaction_history_with(target, INTERACTION_HISTORY_LIMIT)
    history_lines = "\n".join(
        f"[{h['time_label']}][{'你→他' if h['direction'] == 'sent' else '他→你'}] {h['content']}"
        for h in hist)
    msg = generate_chitchat(agent, target, gossip_about, time_label, history_lines)
    if not msg:
        return []

    msgCenter.send_message_by_msg(agent.name, target, msg)
    if BOND_ENABLED and target in agents:
        bonds.update(agent.name, target, CONFIG.get("bond_growth_per_im", 0.03), note="闲聊往来")
    agent.memory_system.log_interaction(target, "sent", msg, time_label)
    if target in agents:
        agents[target].memory_system.log_interaction(agent.name, "received", msg, time_label)
    if EVENT_LOG is not None:
        EVENT_LOG.record(time_label, agent.name, agent.envName,
                         f"向【{target}】发送【{msg}】", msg_to=[target], kind="chitchat")
    return [target]



def process_agent_turn(agent, time_label="", dt_minutes=60, community_names=None, dry_run=False, world=None):
    """处理单个角色的一轮（内层→外层→落库→消息→关系→场景）。
    抽出来供 run_step（回合制）与 continuous_runner（连续时间）共用，
    避免双脑/泄露逻辑在多处重复。单角色异常不影响整场。
    返回 (过滤后的对外文本, 本次闲聊发送目标列表)。"""
    if not hasattr(agent, 'memory_system'):
        return ""
    try:
        # 推进欲望演化（按经过的分钟数缩放，默认 60 分钟=原每轮语义）
        if DESIRE_ENABLED:
            for _line in agent.desire_system.tick(dt_minutes):
                print(f"[欲望变动] {agent.name}：{_line}")

        envInfo = envs.get_env(agent.envName)
        joinable_context = world.get_joinable_context(agent) if world is not None else ""
        action, old_envName, new_envName = agent.get_action(envInfo, time_label, joinable_context=joinable_context, world=world)
        filtered_action = agent.filter_thinking(action)

        print(f"[{time_label}] {agent.name} {agent.envName} ：")
        print(filtered_action)

        # 根据本轮行动，回写"朝哪些惦记迈了步"（重置搁置计数、小幅升温）
        if DESIRE_ENABLED:
            agent.desire_system.note_progress_from_text(filtered_action)

        if msgCenter.send_message_by_action(agent.name, filtered_action):
            print('【发送消息成功】')

        # 主行动里的 IM：关系升温 + 记录跨轮往来
        _im_pairs = _extract_im_pairs(filtered_action)
        _im_targets = [t for t, _ in _im_pairs]
        if BOND_ENABLED:
            for _tgt in _im_targets:
                if _tgt in agents:
                    bonds.update(agent.name, _tgt, CONFIG.get("bond_growth_per_im", 0.03), note="近期有往来")
        for _tgt, _content in _im_pairs:
            agent.memory_system.log_interaction(_tgt, "sent", _content, time_label)
            if _tgt in agents:
                agents[_tgt].memory_system.log_interaction(agent.name, "received", _content, time_label)

        # 结构化事件记录（按场景/按人物两种视图）；由运行时启用
        if EVENT_LOG is not None:
            EVENT_LOG.record(time_label, agent.name, agent.envName, filtered_action,
                             msg_to=_im_targets)

        envs.update_envInfo_by_AI(agent.name, old_envName, agent, filtered_action)
        if new_envName != old_envName:
            envs.update_envInfo_by_AI(agent.name, new_envName, agent, filtered_action)

        # 动森式闲聊层（非任务消息，可跨场景/八卦第三方）
        chitchat_targets = maybe_chitchat(agent, time_label, community_names, dry_run=dry_run)

        print('------------------------------')
        sys.stdout.flush()   # 每个角色处理完即刷盘，便于实时查看与防丢
        return filtered_action, chitchat_targets
    except Exception as e:
        print(f"[ERROR] 角色 {agent.name} 处理失败：{type(e).__name__}: {e}")
        print('------------------------------')
        sys.stdout.flush()
        return "", []


def run_step(time_label=""):
    """回合制一步（增强版）：所有角色各走一次。"""
    for agent in agents.values():
        process_agent_turn(agent, time_label, dt_minutes=60)


def run_global_reflection(time_label=""):
    """对所有角色触发一次周期性反思（参考水濑祈 reflections）。"""
    if not REFLECTION_ENABLED:
        return
    for agent in agents.values():
        if not hasattr(agent, "memory_system"):
            continue
        try:
            # 把当前惦记（含权重/执念/搁置）喂给反思，让模型对照着判断执念与放下
            desire_ctx = ""
            if DESIRE_ENABLED:
                _lines = []
                for d in agent.desire_system.get_active(DESIRE_MAX * 2):
                    tag = "执念" if d["obsession"] else ("搁置" if d.get("since_progress", 0) >= 3 else "要紧")
                    _lines.append(f"- ({tag}{d['weight']:.0%}) {d['content']}")
                if _lines:
                    desire_ctx = "\n".join(_lines)
            res = agent.memory_system.run_reflection(desire_context=desire_ctx)
            if res and DESIRE_ENABLED:
                for d in res.get("desires", []):
                    if agent.desire_system.count_active() < DESIRE_MAX * 3:
                        agent.desire_system.add(d, strength=0.6)
                # 反思生出的执念：命中已有惦记则升为执念，否则作为新执念加入
                for o in res.get("obsessions", []):
                    if agent.desire_system.promote_obsession(o):
                        print(f"[反思-执念] {agent.name}：{o}")
                    elif agent.desire_system.count_active() < DESIRE_MAX * 3:
                        agent.desire_system.add({"content": o, "weight": 0.85, "obsession": True})
                        print(f"[反思-新执念] {agent.name}：{o}")
                # 反思决定放下的旧惦记（执念不会被放下）
                for g in res.get("let_go", []):
                    if agent.desire_system.give_up(g):
                        print(f"[反思-放下] {agent.name}：{g}")
                print(f"[反思] {agent.name}：{(res.get('reflection') or '')[:60]}")
        except Exception as e:
            print(f"[ERROR] 反思 {agent.name} 失败：{type(e).__name__}: {e}")