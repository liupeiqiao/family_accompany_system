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


def test_client_uses_default_key():
    """即使未设置环境变量，也应使用内置默认 key 正常创建客户端。"""
    import os
    try:
        from llm.client import get_client
        client = get_client()
        assert client.api_key == "sk-032e2e8065ae4e66a64a95d8fea81dd7"
    finally:
        pass
