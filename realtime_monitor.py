# -*- coding: utf-8 -*-
"""
realtime_monitor.py —— 实时互动监控系统
==================================================
让角色的互动像直播一样实时展示

功能：
1. 实时显示每个角色的行动
2. 高亮显示角色间的互动（消息、对话）
3. 彩色终端输出，区分不同角色
4. 支持网页模式（HTML实时刷新）

用法：
    python realtime_monitor.py [轮数] [--html]
        - 轮数：运行几轮（默认无限）
        - --html：同时生成HTML网页监控
==================================================
"""
import sys
import os
import time
import datetime
import re
import json
import threading

PROJ = r"D:\致敬传奇AI项目"
sys.path.insert(0, PROJ)
os.chdir(PROJ)

# 角色颜色配置（终端颜色）
ROLE_COLORS = {
    "陈子墨": "\033[96m",    # 青色
    "林阳": "\033[92m",      # 绿色
    "王浩宇": "\033[93m",    # 黄色
    "赵天磊": "\033[95m",    # 紫色
    "孙一凡": "\033[94m",    # 蓝色
    "周景行": "\033[91m",    # 红色
    "班主任": "\033[33m",    # 橙色
    "张老师": "\033[36m",    # 深青色
    "篮球教练": "\033[35m",  # 洋红色
}
DEFAULT_COLOR = "\033[0m"  # 默认颜色
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# 互动关键词
INTERACTION_KEYWORDS = ["向", "发送", "消息", "同意", "好友", "申请"]


def get_color(name):
    """获取角色颜色"""
    return ROLE_COLORS.get(name, DEFAULT_COLOR)


def is_interaction(text):
    """判断是否是互动内容"""
    return any(kw in text for kw in INTERACTION_KEYWORDS)


def print_colored(text, color=DEFAULT_COLOR, bold=False, end="\n"):
    """彩色打印"""
    prefix = BOLD + color if bold else color
    print(f"{prefix}{text}{RESET}", end=end, flush=True)


def print_separator(char="-", length=50):
    """打印分隔线"""
    print_colored(char * length, DIM)


def print_header(text):
    """打印标题"""
    print()
    print_separator("=", 60)
    print_colored(f"  {text}", BOLD, bold=True)
    print_separator("=", 60)


def print_round_header(step, time_label):
    """打印轮次标题"""
    print()
    print_colored(f"+{'=' * 58}+", BOLD)
    print_colored(f"|  第 {step} 轮 | {time_label:<45} |", BOLD, bold=True)
    print_colored(f"+{'=' * 58}+", BOLD)


def print_action(name, env, action, is_interact=False):
    """打印角色行动"""
    color = get_color(name)
    
    # 角色名和场景
    print_colored(f"\n【{name}】", color, bold=True, end="")
    print_colored(f" {env}", DIM)
    
    # 解析并高亮显示行动内容
    lines = action.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 思考部分
        if line.startswith("思考【"):
            print_colored(f"  [思考] {line}", color)
        # 记忆更新
        elif "更新记忆" in line:
            print_colored(f"  [记忆] {line}", "\033[33m")  # 黄色
        # 动作部分
        elif line.startswith("我要") or line.startswith("向"):
            if is_interaction(line):
                print_colored(f"  [消息] {line}", "\033[92m", bold=True)  # 绿色高亮
            else:
                print_colored(f"  [行动] {line}", color)
        # 其他
        else:
            print_colored(f"     {line}", color)


def print_interaction(from_name, to_name, message):
    """打印互动消息"""
    from_color = get_color(from_name)
    to_color = get_color(to_name)
    
    print()
    print_colored(f"  +-----------------------------------------", "\033[92m")
    print_colored(f"  | [消息] 互动消息", "\033[92m", bold=True)
    print_colored(f"  | ", "\033[92m", end="")
    print_colored(f"{from_name}", from_color, bold=True, end="")
    print_colored(f" → ", "\033[92m", end="")
    print_colored(f"{to_name}", to_color, bold=True)
    print_colored(f"  | [发送] {message}", "\033[92m")
    print_colored(f"  +-----------------------------------------", "\033[92m")


def make_time_label(step, start="14:00", hours_per_round=1):
    """生成时间标签"""
    h0, m0 = map(int, start.split(":"))
    total_min = h0 * 60 + m0 + (step - 1) * hours_per_round * 60
    day = total_min // (24 * 60) + 1
    rem = total_min % (24 * 60)
    return f"第{day}天 {rem // 60:02d}:{rem % 60:02d}"


class HTMLMonitor:
    """HTML网页监控器"""
    
    def __init__(self, output_path):
        self.output_path = output_path
        self.events = []
        self.lock = threading.Lock()
        
        # 创建初始HTML
        self._write_html()
    
    def add_event(self, event_type, data):
        """添加事件"""
        with self.lock:
            self.events.append({
                "type": event_type,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                **data
            })
            self._write_html()
    
    def _write_html(self):
        """写入HTML文件"""
        html = self._generate_html()
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html)
    
    def _generate_html(self):
        """生成HTML内容"""
        events_html = ""
        for event in reversed(self.events[-50:]):  # 只显示最近50条
            if event["type"] == "round":
                events_html += f'''
                <div class="event round-header">
                    <div class="time">{event["time"]}</div>
                    <div class="content">=== {event["title"]} ===</div>
                </div>
                '''
            elif event["type"] == "action":
                color = ROLE_COLORS.get(event["name"], "#ffffff").replace("\033[96m", "#00ffff").replace("\033[92m", "#00ff00").replace("\033[93m", "#ffff00").replace("\033[95m", "#ff00ff").replace("\033[94m", "#0000ff").replace("\033[91m", "#ff0000").replace("\033[33m", "#ffaa00").replace("\033[36m", "#00aaaa").replace("\033[35m", "#aa00aa")
                
                is_interact = event.get("is_interaction", False)
                action_class = "interaction" if is_interact else "normal"
                
                events_html += f'''
                <div class="event action {action_class}">
                    <div class="time">{event["time"]}</div>
                    <div class="character" style="color: {color}">{event["name"]}</div>
                    <div class="location">{event["env"]}</div>
                    <div class="content">{event["content"]}</div>
                </div>
                '''
            elif event["type"] == "interaction":
                events_html += f'''
                <div class="event interaction-msg">
                    <div class="time">{event["time"]}</div>
                    <div class="content">
                        [消息] <span class="from">{event["from"]}</span> 
                        → <span class="to">{event["to"]}</span>: 
                        {event["message"]}
                    </div>
                </div>
                '''
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>致敬传奇AI - 实时互动监控</title>
    <meta http-equiv="refresh" content="2">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            font-size: 14px;
            opacity: 0.8;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        .event {{
            background: #16213e;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .round-header {{
            background: linear-gradient(90deg, #667eea, #764ba2);
            text-align: center;
            font-weight: bold;
            font-size: 16px;
        }}
        .action {{
            border-left-color: #00d2ff;
        }}
        .action.interaction {{
            border-left-color: #00ff88;
            background: #1a2e1a;
        }}
        .interaction-msg {{
            border-left-color: #ffaa00;
            background: #2e2a1a;
        }}
        .time {{
            font-size: 12px;
            color: #888;
            margin-bottom: 5px;
        }}
        .character {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 5px;
        }}
        .location {{
            font-size: 12px;
            color: #aaa;
            margin-bottom: 10px;
        }}
        .content {{
            line-height: 1.6;
            white-space: pre-wrap;
        }}
        .from {{ color: #00ffff; font-weight: bold; }}
        .to {{ color: #ff6b6b; font-weight: bold; }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>[戏剧] 致敬传奇AI - 实时互动监控</h1>
            <div class="subtitle">明远中学 302 寝室 | 每2秒自动刷新</div>
        </div>
        <div class="events">
            {events_html if events_html else '<div class="event"><div class="content">等待模拟开始...</div></div>'}
        </div>
        <div class="footer">
            共记录 {len(self.events)} 条事件 | {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
</body>
</html>'''


def run_monitor(rounds=None, html_mode=False):
    """运行实时监控"""
    # 清屏
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print_header("[戏剧] 致敬传奇AI - 实时互动监控")
    print_colored("  明远中学 302 寝室", DIM)
    print_colored("  实时观看角色们的互动...", DIM)
    print()
    
    # 导入项目模块
    import caller as caller_mod
    
    # 重试机制
    _orig = caller_mod.call_model
    def call_with_retry(*a, **kw):
        last = None
        for i in range(4):
            try:
                r = _orig(*a, **kw)
                content = ""
                try:
                    content = r["choices"][0]["message"]["content"] or ""
                except Exception:
                    pass
                if isinstance(r, dict) and "choices" in r and content.strip():
                    return r
                last = r
            except Exception as e:
                last = e
            time.sleep(2)
        if isinstance(last, Exception):
            raise last
        return last
    caller_mod.call_model = call_with_retry
    
    import agent_factory
    import engine
    
    # 加载角色
    config_path = os.path.join(PROJ, "schoolAgents.json")
    agent_factory.load_AuvAgents_from_json(config_path)
    agent_factory.update_envs_with_agents_info()
    
    print_colored(f"  [OK] 已加载 {len(agent_factory.agents)} 个角色", "\033[92m")
    print()
    
    # HTML监控器
    html_monitor = None
    if html_mode:
        html_path = os.path.join(PROJ, "monitor.html")
        html_monitor = HTMLMonitor(html_path)
        print_colored(f"  [监控] 网页监控已启动：{html_path}", "\033[92m")
        print_colored("     请在浏览器中打开此文件查看实时监控", DIM)
        print()
    
    print_separator()
    
    step = 0
    try:
        while True:
            step += 1
            time_label = make_time_label(step)
            
            # 打印轮次标题
            print_round_header(step, time_label)
            if html_monitor:
                html_monitor.add_event("round", {"title": f"第 {step} 轮 | {time_label}"})
            
            # 遍历所有角色
            for agent in agent_factory.agents.values():
                name = agent.name
                env = agent.envName
                env_info = engine.envs.get_env(env)
                
                # 获取行动
                action, old_env, new_env = agent.get_action(env_info, time_label)
                
                # 判断是否是互动
                is_interact = is_interaction(action)
                
                # 终端输出
                print_action(name, env, action, is_interact)
                
                # HTML输出
                if html_monitor:
                    html_monitor.add_event("action", {
                        "name": name,
                        "env": env,
                        "content": action,
                        "is_interaction": is_interact
                    })
                
                # 处理消息
                filtered = agent.filter_thinking(action)
                if engine.msgCenter.send_message_by_action(name, filtered):
                    # 提取消息详情
                    msg_matches = re.findall(r'向【(.+?)】发送【(.+?)】', filtered)
                    for to_name, message in msg_matches:
                        print_interaction(name, to_name, message)
                        if html_monitor:
                            html_monitor.add_event("interaction", {
                                "from": name,
                                "to": to_name,
                                "message": message
                            })
                
                # 更新场景
                engine.envs.update_envInfo_by_AI(name, old_env, agent, filtered)
                if new_env != old_env:
                    engine.envs.update_envInfo_by_AI(name, new_env, agent, filtered)
                
                time.sleep(0.5)  # 短暂延迟，让输出更易读
            
            print_separator()
            print_colored(f"  第 {step} 轮结束", DIM)
            
            # 检查是否达到轮数限制
            if rounds and step >= rounds:
                break
            
            time.sleep(1)  # 轮次间隔
    
    except KeyboardInterrupt:
        print()
        print_header("监控已停止")
        print_colored(f"  共运行 {step} 轮", DIM)
        if html_monitor:
            print_colored(f"  网页监控文件：{html_path}", DIM)


def main():
    args = sys.argv[1:]
    html_mode = "--html" in args
    args = [a for a in args if a != "--html"]
    
    rounds = int(args[0]) if args and args[0].isdigit() else None
    
    run_monitor(rounds, html_mode)


if __name__ == "__main__":
    main()


