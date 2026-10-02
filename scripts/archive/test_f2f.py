# -*- coding: utf-8 -*-
"""隔离测试：f2f 追踪器 + 加入 intent（不调 LLM）。"""
from environment import World


class FakeAgent:
    def __init__(self, name, env):
        self.name = name
        self.envName = env


def main():
    w = World()
    a = FakeAgent('甲', '奶茶店')
    b = FakeAgent('乙', '奶茶店')
    c = FakeAgent('丙', '奶茶店')

    # 甲发起与乙在奶茶店的当面会话
    w.record_face_to_face('奶茶店', ['甲', '乙'], '甲', '12:00')

    # 参与者（甲/乙）看不到"可加入"；旁观者丙能看到
    assert w.get_joinable_context(a) == '', '参与者不应看到可加入'
    assert w.get_joinable_context(b) == '', '参与者不应看到可加入'
    ctx_c = w.get_joinable_context(c)
    assert '甲' in ctx_c and '乙' in ctx_c and '奶茶店' in ctx_c, ctx_c
    print('PASS get_joinable_context:', ctx_c)

    # 模拟丙用 加入【甲】 加入（走 process_action 的解析逻辑）
    import re
    action = '丙凑到甲旁边，加入【甲】一起聊。'
    m = re.search(r'加入【(.+?)】', action)
    assert m and m.group(1) == '甲'
    w.record_face_to_face(c.envName, [c.name, m.group(1)], c.name, '12:05')
    # 现在会话参与者应包含 甲、乙、丙
    talks = w.face_to_face['奶茶店']
    last = talks[-1]
    assert '丙' in last['participants'] and '甲' in last['participants']
    print('PASS 加入记录: participants =', sorted(last['participants']))

    # reset 清空
    w.reset()
    assert w.face_to_face == {}
    print('PASS reset 清空 f2f tracker')

    print('\nALL F2F TESTS PASSED')


if __name__ == '__main__':
    main()
