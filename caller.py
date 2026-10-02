import os
import time
import requests

# 统一从环境变量读取；未设置时回退到内置默认值，便于本地直接运行。
# 说明：内置默认 key（sk-tp-...）为腾讯 LKEAP（大模型知识引擎 Token Plan）的 HY3 key，
# 需配套 LKEAP 端点 https://api.lkeap.cloud.tencent.com/plan/v3 与模型 hy3 使用。
API_KEY = os.environ.get('LLM_API_KEY', os.environ.get('MIMO_API_KEY', 'sk-tp-REDACTED'))
BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.lkeap.cloud.tencent.com/plan/v3/chat/completions')
MODEL = os.environ.get('LLM_MODEL', 'hy3')
MAX_RETRIES = int(os.environ.get('LLM_MAX_RETRIES', '3'))
RETRY_BACKOFF = 2  # 秒，指数退避
TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '180'))  # 单次请求超时（秒），可用环境变量调小以应对 API 挂起


def call_model(messages, model=None, temperature=0.7, stream=False, max_tokens=None):
    """统一的 API 调用：带重试与容错，并支持 max_tokens。"""
    model = model or MODEL
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if max_tokens:
        data["max_tokens"] = max_tokens

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(BASE_URL, headers=headers, json=data, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {last_err}")