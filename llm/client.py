"""DeepSeek V4 Pro API client (OpenAI-compatible)."""

import os
import time
from openai import OpenAI


def get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is required")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return OpenAI(api_key=api_key, base_url=base_url)


MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MAX_RETRIES = 2


def chat(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    client = get_client()
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                timeout=10,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
    raise last_error
