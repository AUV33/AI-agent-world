# -*- coding: utf-8 -*-
import requests
import dns_override

# 本机 DNS 间歇性故障，导入时自动切换到公共 DNS 解析
dns_override.patch()

API_KEY = 'REMOVED_API_KEY'

def call_model(messages, model="mimo-v2.5-pro", temperature=0.7, stream=False, max_tokens=None):
    url = "https://api.xiaomimimo.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream
    }
    if max_tokens:
        data["max_tokens"] = max_tokens
    response = requests.post(url, headers=headers, json=data, timeout=180)
    rsp = response.json()
    if not isinstance(rsp, dict) or "choices" not in rsp or not rsp["choices"]:
        raise RuntimeError("API 返回异常：" + str(rsp)[:300])
    return rsp