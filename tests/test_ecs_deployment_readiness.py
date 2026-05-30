from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_nextjs_package_has_production_start_script():
    package_data = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))

    assert package_data["scripts"]["start"] == "next start"


def test_pm2_ecosystem_runs_backend_and_frontend_on_loopback_ports():
    source = (ROOT / "ecosystem.config.js").read_text(encoding="utf-8")

    assert "family-companion-api" in source
    assert "family-companion-web" in source
    assert "uvicorn" in source
    assert "api.main:app" in source
    assert "127.0.0.1" in source
    assert "8000" in source
    assert "next" in source
    assert "start" in source
    assert "3000" in source


def test_nginx_template_routes_frontend_and_api():
    source = (ROOT / "deploy" / "nginx" / "family-companion.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://127.0.0.1:3000" in source
    assert "proxy_pass http://127.0.0.1:8000" in source
    assert "location /api/" in source
    assert "client_max_body_size" in source


def test_postgres_check_script_loads_env_without_printing_secrets():
    source = (ROOT / "scripts" / "check_postgres.py").read_text(encoding="utf-8")

    assert "load_dotenv" in source
    assert "DATABASE_URL" in source
    assert "JWT_SECRET" in source
    assert "init_schema" in source
    assert "urlparse" in source
    assert "password" not in source.lower()
    assert "JWT_SECRET=" not in source


def test_ecs_deployment_doc_covers_current_manual_flow():
    source = (ROOT / "docs" / "ecs-deployment.md").read_text(encoding="utf-8")

    for expected in [
        "git clone -b 第一版 git@github.com:liupeiqiao/family_accompany_system.git companion",
        "python3 -m pip install -r requirements.txt",
        "npm install",
        "npm run build",
        "pm2 start ecosystem.config.js",
        "scripts/check_postgres.py",
        "family-companion.conf",
        "不要部署旧版 Streamlit",
    ]:
        assert expected in source
