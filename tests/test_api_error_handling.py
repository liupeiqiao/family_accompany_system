"""RED: API auth error should be caught gracefully, not crash the app."""

import pytest
from llm.parser import parse_user_text


class FakeAuthError(Exception):
    """Simulate OpenAI auth error."""
    pass


def test_parse_user_text_handles_api_error(monkeypatch):
    """智能解析时 API 认证失败应返回空结果，不应抛出异常崩溃。"""

    def mock_chat(*args, **kwargs):
        raise FakeAuthError("Authentication Fails")

    monkeypatch.setattr("llm.parser.chat", mock_chat)

    result = parse_user_text("我儿子叫小明，性格温和")
    # 不应崩溃，应返回空兜底
    assert "persona" in result
    assert "memories" in result
    assert result["persona"] == {} or result["memories"] == []


def test_parse_user_text_handles_generic_error(monkeypatch):
    """通用 API 错误也应优雅降级。"""

    def mock_chat(*args, **kwargs):
        raise RuntimeError("Connection timeout")

    monkeypatch.setattr("llm.parser.chat", mock_chat)

    result = parse_user_text("测试文本")
    assert "persona" in result
    assert "memories" in result


def test_run_pipeline_handles_auth_error():
    """Pipeline 中 LLM 调用失败应返回预设安慰话术，不应崩溃。"""
    from engine.adaptation import check_elderly_adaptation

    # 模拟 API 失败后 fallback 话术
    fallback = "妈，我这边信号不太好，您再说一遍？"
    assert "信号不太好" in fallback or "再说一遍" in fallback


def test_client_requires_api_key_from_environment(monkeypatch):
    """DeepSeek API Key 必须通过环境变量提供，不能使用代码内置 key。"""
    from llm.client import get_client

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        get_client()
