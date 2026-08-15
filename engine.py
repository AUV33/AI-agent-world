from caller import call_model
import re

agents = {}

def getContent(rsp):
    try:
        return rsp['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        return ''

class Agent:
    def __init__(self, name, persona, envName, memory="", impressions=None):
        self.name = name
        self.memory = memory
        self.persona = persona
        self.envName = envName
        self.addressBook = set()
        self.impressions = impressions or {}

    def get_addressBook_str(self):
        return ','.join(self.addressBook)

    def get_action(self, envInfo, time_label=""):
        system_prompt = f'现在是{time_label}。你叫{self.name}，你是{self.persona[:950]}，你在{self.envName}。输出三部分：1.思考【思考内容】2.更新记忆【新的记忆】3.接下来一小时的动作（思考不等于行动，行动要具体重复给出）。世界场景：{envs.get_all_envNameStr()}。要在当前场景做事就直接说要做什么；要移动用"我要前往【场景名】"，目标必须与场景列表一字不差，禁止向不存在或当前所在场景移动，远距离移动耗费大量金钱请慎重。你有人设里写的劣根性——这是人性的一部分，不是什么见不得人的事。但你会看场合表现：老师、家长、喜欢的人面前或公共场合收敛，兄弟面前、没人注意、涉及面子或利益时流露。记住：圣人不存在，每个人都戴着面具生活。注意，请全程用第三人称叙述自己（用全名或"他/她"），不要出现"我"字。'
        full_context = f"你的记忆是：{self.memory}\n\n你在{self.envName}看到了：{envInfo}，需要特别注意，场景中有你想要互动的人时才能进行互动，不要和不存在的人进行互动。如果你找不到你要互动的人，你可以使用IM给他发送消息，现在你的通讯录中有：{self.get_addressBook_str()}，发送消息用格式“向【联系人名】发送【消息内容】”，如果你的通讯录中没有你想联系的人，你可以发送“向【联系人名】发送【申请好友】。”注意括号【】不能省略！！"
        
        if self.impressions:
            imp_txt = "；".join(f"你对{who}的印象：{imp}" for who, imp in self.impressions.items())
            full_context += (f"\n\n{imp_txt}。注意：你对每个人的印象不同，所以对每个人说话方式、态度、"
                             f"亲近程度也不同——有人让你信任、有人让你防备、有人让你不耐烦、有人让你想亲近。"
                             f"请依据你对每个人的印象，用不同的风格和他们相处。")
        new_im_message = msgCenter.get_padding_msg(self.name)
        if new_im_message:
            full_context += f"\n\n你IM中收到了新消息：{new_im_message}，使用“向【联系人名】发送【消息内容】”格式回复消息。如果收到的消息是申请好友请求，你可以直接用“同意【联系人名】的好友请求”格式来同意，如果拒绝，则不需要回复。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_context}
        ]
        response = call_model(messages, max_tokens=1000)
        action = getContent(response)
        old_envName = self.envName
        self.process_action(action)
        return action, old_envName, self.envName

    def process_action(self, action):
        memory_match = re.search(r'更新记忆【(.+?)】', action)
        if memory_match:
            new_mem = memory_match.group(1).strip()
            if new_mem:
                self.memory = (self.memory + "；" + new_mem) if self.memory else new_mem
                if len(self.memory) > 600:
                    self.memory = self.memory[-600:]
        env_match = re.search(r'我要前往【(.+?)】', action)
        if not env_match:
            env_match = re.search(r'我要前往(.+?)。', action)
        if env_match:
            self.update_envName(env_match.group(1))

    def filter_thinking(self, action):
        action = re.sub(r'思考【.*?】', '', action)
        action = re.sub(r'更新记忆【.*?】', '', action)
        return action.strip()

    def update_envName(self, newEnvName):
        if newEnvName in envs.get_all_envNameList():
            self.envName = newEnvName


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
        response = call_model(messages, max_tokens=500)
        new_info = getContent(response)
        if new_info and new_info.strip():
            self.update_envInfo_by_str(envName, new_info)
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


def run_step(time_label=""):
    for agent in agents.values():
        print(f"[{time_label}] {agent.name} {agent.envName} ：")
        envInfo = envs.get_env(agent.envName)
        action, old_envName, new_envName = agent.get_action(envInfo, time_label)
        print(action)

        filtered_action = agent.filter_thinking(action)
        if msgCenter.send_message_by_action(agent.name, filtered_action):
            print('【发送消息成功】')

        print(old_envName, '：')
        envInfo = envs.update_envInfo_by_AI(agent.name, old_envName, agent, filtered_action)
        print(envInfo)

        if new_envName != old_envName:
            print(new_envName, '：')
            newEnvInfo = envs.update_envInfo_by_AI(agent.name, new_envName, agent, filtered_action)
            print(newEnvInfo)

        print('------------------------------')
        

