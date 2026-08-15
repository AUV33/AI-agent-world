# -*- coding: utf-8 -*-
"""
demo_enhanced.py —— 增强版系统演示
==================================================
运行这个脚本体验增强版效果
==================================================
"""
import sys
import os
import time
import datetime

PROJ = r"D:\致敬传奇AI项目"
sys.path.insert(0, PROJ)
os.chdir(PROJ)

# 颜色定义
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
RED = "\033[91m"
BLUE = "\033[94m"


def print_header(text):
    print()
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")


def print_section(text):
    print()
    print(f"{BOLD}{CYAN}┌{'─' * 58}┐{RESET}")
    print(f"{BOLD}{CYAN}│  {text:<56}│{RESET}")
    print(f"{BOLD}{CYAN}└{'─' * 58}┘{RESET}")


def print_agent_info(name, color, info):
    print(f"\n{color}{BOLD}【{name}】{RESET}")
    for key, value in info.items():
        print(f"  {DIM}{key}：{RESET}{value}")


def make_time_label(step, start="14:00", hours_per_round=1):
    h0, m0 = map(int, start.split(":"))
    total_min = h0 * 60 + m0 + (step - 1) * hours_per_round * 60
    day = total_min // (24 * 60) + 1
    rem = total_min % (24 * 60)
    return f"第{day}天 {rem // 60:02d}:{rem % 60:02d}"


def main():
    print_header("[戏剧] 致敬传奇AI - 增强版系统演示")
    print(f"\n{DIM}  参考智能体水濑祈架构，展示增强版效果{RESET}")
    print(f"{DIM}  包含：记忆系统、情绪系统、生活状态、思考日志{RESET}")
    
    # 导入系统
    print(f"\n{YELLOW}  正在加载系统...{RESET}")
    
    from enhanced_memory import EnhancedMemory
    from emotion_system import EmotionSystem
    from life_state import LifeState
    from thinking_logger import ThinkingLogger
    
    print(f"{GREEN}  [OK] 系统加载完成{RESET}")
    
    # 演示角色
    agents_config = [
        {"name": "陈子墨", "color": CYAN, "persona": "18岁，高二(3)班学生，302寝室1号床，成绩不错的普通学霸"},
        {"name": "林阳", "color": GREEN, "persona": "18岁，高二(3)班学生，302寝室2号床，校篮球队主力前锋"},
        {"name": "王浩宇", "color": YELLOW, "persona": "18岁，高二(3)班学生，302寝室3号床，成绩拉垮的网瘾少年"},
    ]
    
    # 初始化各个系统
    print_section("[图表] 系统初始化")
    
    memories = {}
    emotions = {}
    life_states = {}
    thinking_loggers = {}
    
    for config in agents_config:
        name = config["name"]
        memories[name] = EnhancedMemory(name, db_path=os.path.join(PROJ, "demo_memory.db"))
        emotions[name] = EmotionSystem(name, state_file=os.path.join(PROJ, f"demo_emotion_{name}.json"))
        life_states[name] = LifeState(name, state_file=os.path.join(PROJ, f"demo_life_{name}.json"))
        thinking_loggers[name] = ThinkingLogger(name, log_file=os.path.join(PROJ, f"demo_thinking_{name}.jsonl"))
        
        # 设置初始情绪
        if name == "陈子墨":
            emotions[name].update("calm", 0.3, "平静的一天")
        elif name == "林阳":
            emotions[name].update("happy", 0.5, "篮球训练很顺利")
        elif name == "王浩宇":
            emotions[name].update("happy", 0.4, "偷偷打了会游戏")
        
        print(f"  {config['color']}[OK] {name}{RESET} - 系统初始化完成")
    
    # 演示各系统
    print_section("[大脑] 记忆系统演示")
    
    # 陈子墨的记忆
    memories["陈子墨"].add_fact("今天月考成绩出来了，数学考了135分", category="experience")
    memories["陈子墨"].add_fact("林阳篮球比赛赢了，全寝都很高兴", category="experience")
    memories["陈子墨"].add_thought("其实我有点羡慕林阳的洒脱，但我不会承认的")
    memories["陈子墨"].update_impression("林阳", "看着吊儿郎当，偏偏成绩还不错，让人憋屈", 60)
    memories["陈子墨"].update_impression("王浩宇", "成绩拉垮，邋遢，但偶尔抄他作业挺方便", 40)
    
    print(f"\n  {CYAN}陈子墨的记忆上下文：{RESET}")
    context = memories["陈子墨"].get_context()
    for line in context.split("\n")[:8]:
        print(f"    {line}")
    
    print_section("[开心] 情绪系统演示")
    
    # 模拟情绪变化
    print(f"\n  {YELLOW}模拟情绪变化...{RESET}")
    
    # 陈子墨：考试考得好
    emotions["陈子墨"].update("happy", 0.6, "数学考了135分")
    print(f"  {CYAN}陈子墨{RESET}：考试考得好 → {emotions['陈子墨'].get_label()}")
    
    # 林阳：比赛赢了
    emotions["林阳"].update("excited", 0.7, "篮球比赛赢了")
    print(f"  {GREEN}林阳{RESET}：比赛赢了 → {emotions['林阳'].get_label()}")
    
    # 王浩宇：被老师批评
    emotions["王浩宇"].update("sad", 0.5, "被班主任抓到玩手机")
    print(f"  {YELLOW}王浩宇{RESET}：被批评 → {emotions['王浩宇'].get_label()}")
    
    # 显示情绪详情
    print(f"\n  {DIM}情绪详情：{RESET}")
    for name in ["陈子墨", "林阳", "王浩宇"]:
        emotion = emotions[name]
        state = emotion.get_state()
        mood = emotion.get_mood_modifier()
        print(f"    {name}：心情系数 {mood:+.2f} | 快乐={state['happiness']:.2f} 悲伤={state['sadness']:.2f} 愤怒={state['anger']:.2f}")
    
    print_section("[房子] 生活状态演示")
    
    # 显示当前状态
    print(f"\n  {DIM}当前生活状态：{RESET}")
    for name in ["陈子墨", "林阳", "王浩宇"]:
        state = life_states[name].get_current_state()
        context = life_states[name].get_context_string()
        print(f"    {name}：{context}")
    
    print_section("[思考] 思考日志演示")
    
    # 模拟思考记录
    thinking_loggers["陈子墨"].log(
        messages=["林阳问你要不要一起打球"],
        think="其实我想去，但是作业还没写完...算了，还是拒绝吧，反正我也不是特别擅长运动",
        reply="不了，我还有作业没写完"
    )
    
    thinking_loggers["林阳"].log(
        messages=["陈子墨拒绝了打球邀请"],
        think="他肯定又在刷题，书呆子...不过他成绩确实好，有点羡慕",
        reply="行吧，那我自己去练会儿"
    )
    
    print(f"\n  {DIM}思考记录示例：{RESET}")
    print(f"    {CYAN}陈子墨{RESET}：")
    print(f"      思考：其实我想去，但是作业还没写完...")
    print(f"      回复：不了，我还有作业没写完")
    print(f"    {GREEN}林阳{RESET}：")
    print(f"      思考：他肯定又在刷题，书呆子...")
    print(f"      回复：行吧，那我自己去练会儿")
    
    # 分析思考模式
    analysis = thinking_loggers["陈子墨"].analyze()
    print(f"\n  {DIM}思考分析：{RESET}")
    print(f"    记录数：{analysis['total']}")
    print(f"    思考率：{analysis['think_rate']:.0%}")
    
    print_section("[戏剧] 综合演示：角色行动")
    
    # 模拟一轮完整的角色行动
    print(f"\n  {YELLOW}模拟第1轮行动...{RESET}")
    
    time_label = make_time_label(1)
    print(f"\n  {BOLD}═══ {time_label} ═══{RESET}")
    
    # 陈子墨的行动
    print(f"\n  {CYAN}{BOLD}【陈子墨】{RESET} {DIM}教学楼-高二(3)班{RESET}")
    print(f"    {DIM}情绪：{emotions['陈子墨'].get_label()}{RESET}")
    print(f"    {DIM}状态：{life_states['陈子墨'].get_current_state()['activity']}{RESET}")
    print(f"    [思考] 思考【数学考得不错，心情挺好。林阳好像在找人打球，但我得把英语作业写完...】")
    print(f"    [记忆] 更新记忆【月考数学135分，心情不错】")
    print(f"    [行动] 继续写英语作业，偶尔抬头看看窗外")
    
    # 林阳的行动
    print(f"\n  {GREEN}{BOLD}【林阳】{RESET} {DIM}操场{RESET}")
    print(f"    {DIM}情绪：{emotions['林阳'].get_label()}{RESET}")
    print(f"    {DIM}状态：{life_states['林阳'].get_current_state()['activity']}{RESET}")
    print(f"    [思考] 思考【比赛赢了真爽！找陈子墨打球他不来，那就自己练会儿吧...】")
    print(f"    [记忆] 更新记忆【篮球比赛赢了，全寝都很高兴】")
    print(f"    [行动] 在操场练习三分球")
    
    # 王浩宇的行动
    print(f"\n  {YELLOW}{BOLD}【王浩宇】{RESET} {DIM}宿舍楼-302寝室{RESET}")
    print(f"    {DIM}情绪：{emotions['王浩宇'].get_label()}{RESET}")
    print(f"    {DIM}状态：{life_states['王浩宇'].get_current_state()['activity']}{RESET}")
    print(f"    [思考] 思考【被班主任抓到了，真倒霉...手机也被没收了，今晚怎么过啊...】")
    print(f"    [记忆] 更新记忆【被班主任抓到玩手机，手机被没收】")
    print(f"    [行动] 躺在床上发呆，想着怎么跟老妈交代")
    
    # 互动演示
    print_section("[消息] 互动演示")
    
    print(f"\n  {DIM}模拟角色间互动：{RESET}")
    print(f"\n  {GREEN}林阳{RESET} → {CYAN}陈子墨{RESET}：数学考得不错啊，请客！")
    print(f"  {CYAN}陈子墨{RESET} → {GREEN}林阳{RESET}：随便...你篮球不也赢了吗")
    print(f"  {YELLOW}王浩宇{RESET} → {GREEN}林阳{RESET}：阳哥，手机借我玩会儿呗")
    print(f"  {GREEN}林阳{RESET} → {YELLOW}王浩宇{RESET}：滚，自己想办法")
    
    # 保存状态
    print_section("[保存] 保存状态")
    
    for name in ["陈子墨", "林阳", "王浩宇"]:
        emotions[name].save()
        life_states[name].save()
    
    print(f"\n  {GREEN}[OK] 所有状态已保存{RESET}")
    
    # 总结
    print_section("[图表] 系统总结")
    
    print(f"""
  {BOLD}增强版系统特性：{RESET}
  
  1. {CYAN}记忆系统{RESET}：SQLite持久化，支持长期事实、内心想法、人际关系
  2. {GREEN}情绪系统{RESET}：多维度情绪跟踪，会根据事件自动变化
  3. {YELLOW}生活状态{RESET}：模拟真实作息，上课/吃饭/睡觉/自由活动
  4. {PURPLE}思考日志{RESET}：记录内心思考过程，支持分析
  
  {BOLD}与原系统的区别：{RESET}
  
  {DIM}原系统：{RESET}角色只是执行动作的机器
  {DIM}增强版：{RESET}角色有情绪、有记忆、有作息、有内心思考
  """)
    
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  演示完成！{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")


if __name__ == "__main__":
    main()




