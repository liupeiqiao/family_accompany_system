from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auth_library_persists_user_and_exposes_session_helpers():
    auth_source = (ROOT / "web" / "src" / "lib" / "auth.ts").read_text(encoding="utf-8")

    assert "AUTH_USER_KEY" in auth_source
    assert "getAuthUser" in auth_source
    assert "setAuthSession" in auth_source
    assert "clearAuthSession" in auth_source
    assert "window.localStorage.setItem(AUTH_USER_KEY" in auth_source
    assert "window.localStorage.removeItem(AUTH_USER_KEY)" in auth_source


def test_login_page_redirects_when_already_logged_in_and_to_elder_after_login():
    login_source = (ROOT / "web" / "src" / "app" / "login" / "page.tsx").read_text(encoding="utf-8")

    assert "getAuthToken" in login_source
    assert 'router.replace("/elder")' in login_source
    assert 'router.replace("/family")' not in login_source


def test_protected_pages_redirect_to_login_without_token():
    protected_routes = ["family", "records", "voices", "history", "elder"]
    for route in protected_routes:
        source = (ROOT / "web" / "src" / "app" / route / "page.tsx").read_text(encoding="utf-8")
        assert "getAuthToken" in source, route
        assert 'router.replace("/login")' in source, route


def test_home_page_shows_login_state_and_logout_action():
    home_source = (ROOT / "web" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert '"use client";' in home_source
    assert "getAuthUser" in home_source
    assert "clearAuthSession" in home_source
    assert "退出登录" in home_source


def test_home_page_prioritizes_elder_voice_companion_after_login():
    home_source = (ROOT / "web" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert 'href="/elder"' in home_source
    assert "开始语音陪伴" in home_source
    assert "家属管理" in home_source
    assert home_source.index('href: "/elder"') < home_source.index('href: "/family"')


def test_family_page_guides_first_setup_and_next_steps():
    family_source = (ROOT / "web" / "src" / "app" / "family" / "page.tsx").read_text(encoding="utf-8")

    assert "下一步" in family_source
    assert "完善档案与记忆" in family_source
    assert "管理家人音色" in family_source
    assert "查看对话历史" in family_source
    assert "进入老人端" in family_source
    assert 'href: "/records"' in family_source
    assert 'href: "/voices"' in family_source
    assert 'href: "/history"' in family_source
    assert 'href: "/elder"' in family_source
