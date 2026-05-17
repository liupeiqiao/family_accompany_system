"""DeepSeek V4 Pro API client (OpenAI-compatible)."""

import os
from openai import OpenAI


def get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return OpenAI(api_key=api_key, base_url=base_url)


MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def chat(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content
