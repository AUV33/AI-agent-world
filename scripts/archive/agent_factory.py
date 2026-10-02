import json
from engine import Agent, Environment, envs, agents, run_step

def load_JecAgents_from_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        agents_data = json.load(f)
    
    
    env_names = set()
    
    for data in agents_data:
        env_name = f"日本电子专门学校-{data['初始位置']}"
        if env_name not in env_names:
            envs.add_env(env_name, '')
            env_names.add(env_name)
        
        agent = Agent(
            name = data['name'],
            persona = '日本电子专门学校的' + data['persona'],
            envName = env_name
        )
        agents[data['name']] = agent
    

def load_AuvAgents_from_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        agents_data = json.load(f)
    
    
    env_names = set()
    
    for data in agents_data:
        env_name = data['初始位置']
        if env_name not in env_names:
            envs.add_env(env_name, '')
            env_names.add(env_name)
        
        agent = Agent(
            name = data['name'],
            persona = data['persona'],
            envName = env_name
        )
        if 'memory' in data:
            agent.memory = data['memory']
        if 'addressBook' in data:
            agent.addressBook = set(data['addressBook'])
        agents[data['name']] = agent
    

def group_agents_by_environment():
    env_agents = {}
    for agent in agents.values():
        env_name = agent.envName
        if env_name not in env_agents:
            env_agents[env_name] = []
        env_agents[env_name].append(agent)
    return env_agents


def update_envs_with_agents_info():
    env_agents = group_agents_by_environment()
    for env_name, agent_list in env_agents.items():
        agent_names = [a.name for a in agent_list]
        agents_info = f"场景中有: {', '.join(agent_names)}"
        envs.update_envInfo_by_str(env_name, agents_info)


if __name__ == "__main__":
    # load_JecAgents_from_json('JecAgents.json')
    load_AuvAgents_from_json('japanAgents.json')
    update_envs_with_agents_info()
    while True:
        run_step()
