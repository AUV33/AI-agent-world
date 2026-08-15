# -*- coding: utf-8 -*-
"""
demo_simple.py —— 简单演示（不需要API调用）
==================================================
展示增强版系统的效果
==================================================
"""
import sys
import os
import time

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


def print_header(text):
    print()
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")


def print_section(text):
    print()
    print(f"{BOLD}{CYAN}+{'-' * 58}+{RESET}")
    print(f"{BOLD}{CYAN}|  {text:<56}|{RESET}")
    print(f"{BOLD}{CYAN}+{'-' * 58}+{RESET}")


def main():
    print_header("致敬传奇AI - 增强版系统演示")
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
    agents = [
        {"name": "陈子墨", "color": CYAN, "persona": "18岁，高二(3)班学生，302寝室1号床，成绩不错的普通学霸"},
        {"name": "林阳", "color": GREEN, "persona": "18岁，高二(3)班学生，302寝室2号床，校篮球队主力前锋"},
        {"name": "王浩宇", "color": YELLOW, "persona": "18岁，高二(3)班学生，302寝室3号床，成绩拉垮的网瘾少年"},
    ]
    
    # 初始化各个系统
    print_section("系统初始化")
    
    for agent in agents:
        name = agent["name"]
        print(f"  {agent['color']}[OK] {name}{RESET} - 系统初始化完成")
    
    # 演示记忆系统
    print_section("记忆系统演示")
    
    print(f"\n  {CYAN}陈子墨的记忆：{RESET}")
    print(f"    [重要事实] 今天月考成绩出来了，数学考了135分")
    print(f"    [重要事实] 林阳篮球比赛赢了，全寝都很高兴")
    print(f"    [内心想法] 其实我有点羡慕林阳的洒脱，但我不会承认的")
    print(f"    [印象] 对林阳：看着吊儿郎当，偏偏成绩还不错，让人憋屈")
    print(f"    [印象] 对王浩宇：成绩拉垮，邋遢，但偶尔抄他作业挺方便")
    
    # 演示情绪系统
    print_section("情绪系统演示")
    
    print(f"\n  {YELLOW}模拟情绪变化...{RESET}")
    print(f"  {CYAN}陈子墨{RESET}：考试考得好 -> 开心（快乐=0.92）")
    print(f"  {GREEN}林阳{RESET}：比赛赢了 -> 开心（快乐=1.00）")
    print(f"  {YELLOW}王浩宇{RESET}：被批评 -> 难过（悲伤=0.95）")
    
    print(f"\n  {DIM}情绪详情：{RESET}")
    print(f"    陈子墨：心情系数 +0.40 | 积极")
    print(f"    林阳：心情系数 +0.40 | 积极")
    print(f"    王浩宇：心情系数 -0.55 | 消极")
    
    # 演示生活状态
    print_section("生活状态演示")
    
    print(f"\n  {DIM}当前生活状态：{RESET}")
    print(f"    陈子墨：当前状态：啃面包（在食堂，刚刚开始）")
    print(f"    林阳：当前状态：啃面包（在食堂，刚刚开始）")
    print(f"    王浩宇：当前状态：啃面包（在食堂，刚刚开始）")
    
    # 演示思考日志
    print_section("思考日志演示")
    
    print(f"\n  {DIM}思考记录示例：{RESET}")
    print(f"    {CYAN}陈子墨{RESET}：")
    print(f"      思考：其实我想去，但是作业还没写完...")
    print(f"      回复：不了，我还有作业没写完")
    print(f"    {GREEN}林阳{RESET}：")
    print(f"      思考：他肯定又在刷题，书呆子...")
    print(f"      回复：行吧，那我自己去练会儿")
    
    # 演示角色行动
    print_section("角色行动演示")
    
    print(f"\n  {YELLOW}模拟第1轮行动...{RESET}")
    print(f"\n  {BOLD}=== 第1天 14:00 ==={RESET}")
    
    print(f"\n  {CYAN}{BOLD}【陈子墨】{RESET} {DIM}教学楼-高二(3)班{RESET}")
    print(f"    {DIM}情绪：开心{RESET}")
    print(f"    {DIM}状态：啃面包{RESET}")
    print(f"    [思考] 思考【数学考得不错，心情挺好。林阳好像在找人打球，但我得把英语作业写完...】")
    print(f"    [记忆] 更新记忆【月考数学135分，心情不错】")
    print(f"    [行动] 继续写英语作业，偶尔抬头看看窗外")
    
    print(f"\n  {GREEN}{BOLD}【林阳】{RESET} {DIM}操场{RESET}")
    print(f"    {DIM}情绪：开心{RESET}")
    print(f"    {DIM}状态：啃面包{RESET}")
    print(f"    [思考] 思考【比赛赢了真爽！找陈子墨打球他不来，那就自己练会儿吧...】")
    print(f"    [记忆] 更新记忆【篮球比赛赢了，全寝都很高兴】")
    print(f"    [行动] 在操场练习三分球")
    
    print(f"\n  {YELLOW}{BOLD}【王浩宇】{RESET} {DIM}宿舍楼-302寝室{RESET}")
    print(f"    {DIM}情绪：难过{RESET}")
    print(f"    {DIM}状态：啃面包{RESET}")
    print(f"    [思考] 思考【被班主任抓到了，真倒霉...手机也被没收了，今晚怎么过啊...】")
    print(f"    [记忆] 更新记忆【被班主任抓到玩手机，手机被没收】")
    print(f"    [行动] 躺在床上发呆，想着怎么跟老妈交代")
    
    # 演示互动
    print_section("互动演示")
    
    print(f"\n  {DIM}模拟角色间互动：{RESET}")
    print(f"\n  {GREEN}林阳{RESET} -> {CYAN}陈子墨{RESET}：数学考得不错啊，请客！")
    print(f"  {CYAN}陈子墨{RESET} -> {GREEN}林阳{RESET}：随便...你篮球不也赢了吗")
    print(f"  {YELLOW}王浩宇{RESET} -> {GREEN}林阳{RESET}：阳哥，手机借我玩会儿呗")
    print(f"  {GREEN}林阳{RESET} -> {YELLOW}王浩宇{RESET}：滚，自己想办法")
    
    # 系统总结
    print_section("系统总结")
    
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
    
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  演示完成！{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")


if __name__ == "__main__":
    main()
