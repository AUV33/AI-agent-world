"""engine.py - 共享世界基础设施（被 enhanced_* 模块复用）。

提供：场景管理 Environment/envs、即时通讯 IM/msgCenter、全局角色注册表 agents、
以及 getContent 响应解析。基础 Agent / run_step 已废弃，由 enhanced_engine 取代。
"""
from caller import call_model
import re

agents = {}

def getContent(rsp):
    try:
        return rsp['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError, AttributeError):
        return ''

class Environment:
    def __init__(self):
        self.env = {} # key为envName，value为envInfo

    def add_env(self, envName, envInfo):
        if envInfo == None or envInfo == '':
            envInfo = '这里没有人'
        self.env[envName] = envInfo

    def get_env(self, envName):
        return self.env.get(envName, None)

    def get_all_envNameList(self):
        return list(self.env.keys())

    def get_all_envNameStr(self):
        return ','.join(self.env.keys())

    def update_envInfo_by_str(self, envName, newEnvInfo):
        self.env[envName] = newEnvInfo

    def update_envInfo_by_AI(self, agentName, envName, agentObj, agentActionStr):
        warning = '注意！！1.如果角色离开了该场景，他的信息不需要在该场景中体现。2.不要把角色的心理活动更新到场景状态！！！角色说的话要完整更新到场景状态！但不要自行捏造角色没有说过的话！！'
        system_prompt = f'现在有一个场景{envName}，你需要根据场景中先前的状态和新发生的事，更新场景的状态。{warning}'
        envInfo = self.get_env(envName)
        full_context = f'场景中先前的状态是：{envInfo}。{agentObj.name}刚刚{agentName}做了{agentActionStr}。你直接输出场景的新状态，{warning}'
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_context}
        ]
        response = call_model(messages)
        self.update_envInfo_by_str(envName, getContent(response))
        return self.get_env(envName)

envs = Environment()

class IM:
    def __init__(self):
        self.paddingMsgList = {}

    def send_message_by_msg(self, fromName, toName, message):
        self.paddingMsgList[fromName + '_to_' + toName] = message

    def send_message_by_action(self, fromName, action):
        matches = re.findall(r'向【(.+?)】发送【(.+?)】', action)
        if len(matches) == 0:
            matches = re.findall(r'向(.+?)发送【(.+?)】', action)

        sent = False
        if len(matches) > 0:
            for match in matches:
                toName = match[0]
                message = match[1]
                self.send_message_by_msg(fromName, toName, message)
                sent = True
        return sent

    def get_padding_msg(self, toName):
        allMsg = []
        keys_to_remove = []
        for key in self.paddingMsgList:
            names = key.split('_to_')
            if names[1] == toName:
                fromName = names[0]
                allMsg.append(fromName + '：' + self.paddingMsgList[key])
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.paddingMsgList[key]

        ret = '；'.join(allMsg)
        if ret != '' and ret != '[]':
            return ret

    def process_add_friend(self, name, action):
        match = re.search(r'同意【(.+?)】的好友请求', action)
        if match:
            friend_name = match.group(1)
            if name and friend_name:
                agents[friend_name].addressBook.add(name)
                agents[name].addressBook.add(friend_name)

msgCenter = IM()



