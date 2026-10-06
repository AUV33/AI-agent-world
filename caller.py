import os
import time
import requests

from llm_record import RECORDER


def _load_dotenv():
    """从项目根目录的 .env 读取环境变量（若存在）。密钥不入库，仅本地使用。"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v


_load_dotenv()

# 统一从环境变量读取密钥，不把任何密钥硬编码进仓库。
# 默认使用腾讯 LKEAP（大模型知识引擎 Token Plan）的 HY3 端点与模型 hy3；
# 运行前请设置环境变量 LLM_API_KEY（或 MIMO_API_KEY）。可参考 .env.example。
API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('MIMO_API_KEY') or ''
BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.lkeap.cloud.tencent.com/plan/v3/chat/completions')
MODEL = os.environ.get('LLM_MODEL', 'hy3')
MAX_RETRIES = int(os.environ.get('LLM_MAX_RETRIES', '3'))
RETRY_BACKOFF = 2  # 秒，指数退避
TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '180'))  # 单次请求超时（秒），可用环境变量调小以应对 API 挂起


def call_model(messages, model=None, temperature=0.7, stream=False, max_tokens=None):
    """统一的 API 调用：带重试与容错，并支持 max_tokens。

    录放层（llm_record.py）先手：replay 命中就直接返回，**不需要密钥、不联网**；
    replay 未命中默认抛错（拒绝偷偷联网）。off 模式完全不介入，行为与接入前一致。
    """
    model = model or MODEL
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if max_tokens:
        data["max_tokens"] = max_tokens

    # 键里带上端点：换了接口就不该静默命中旧记录
    _rec_key = RECORDER.begin(data, extra=BASE_URL)
    if _rec_key is not None:
        _hit = RECORDER.lookup(_rec_key)
        if _hit is not None:
            return _hit
        RECORDER.on_miss(_rec_key, data)

    if not API_KEY:
        raise RuntimeError(
            "未设置 LLM_API_KEY（或 MIMO_API_KEY）环境变量，无法调用模型。\n"
            "密钥不入库：请通过环境变量或 .env 文件提供（参考 .env.example）。"
        )
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(BASE_URL, headers=headers, json=data, timeout=TIMEOUT)
            response.raise_for_status()
            _resp = response.json()
            if _rec_key is not None:
                RECORDER.store(_rec_key, data, _resp)
            return _resp
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {last_err}")