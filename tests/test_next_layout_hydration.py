from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_html_suppresses_extension_hydration_warning():
    layout = (ROOT / "web" / "src" / "app" / "layout.tsx").read_text(
        encoding="utf-8"
    )

    assert "suppressHydrationWarning" in layout
    assert '<html lang="zh-CN" suppressHydrationWarning>' in layout
