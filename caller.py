# -*- coding: utf-8 -*-
import requests
import dns_override

# 鏈満 DNS 闂存瓏鎬ф晠闅滐紝瀵煎叆鏃惰嚜鍔ㄥ垏鎹㈠埌鍏叡 DNS 瑙ｆ瀽
dns_override.patch()

import os
API_KEY = os.environ.get('MIMO_API_KEY', '')

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
        raise RuntimeError("API 杩斿洖寮傚父锛? + str(rsp)[:300])
    return rsp
