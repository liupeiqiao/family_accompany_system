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


def test_login_page_redirects_when_already_logged_in_and_to_family_after_login():
    login_source = (ROOT / "web" / "src" / "app" / "login" / "page.tsx").read_text(encoding="utf-8")

    assert "getAuthToken" in login_source
    assert 'router.replace("/")' in login_source
    assert 'router.replace("/family")' in login_source


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
