from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_nextjs_package_has_production_start_script():
    package_data = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))

    assert package_data["scripts"]["start"] == "next start"


def test_pm2_ecosystem_runs_backend_and_frontend_on_loopback_ports():
    source = (ROOT / "ecosystem.config.js").read_text(encoding="utf-8")

    assert "companion-api" in source
    assert "companion-web" in source
    assert "uvicorn" in source
    assert "api.main:app" in source
    assert "127.0.0.1" in source
    assert "8000" in source
    assert "next" in source
    assert "start" in source
    assert "3000" in source
    assert 'COMPANION_ENV: "production"' in source
    assert "DATABASE_URL" not in source
    assert "JWT_SECRET" not in source


def test_nginx_template_routes_frontend_and_api():
    source = (ROOT / "deploy" / "nginx" / "family-companion.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://127.0.0.1:3000" in source
    assert "proxy_pass http://127.0.0.1:8000" in source
    assert "location /api/" in source
    assert "client_max_body_size" in source


def test_api_health_endpoint_reports_cloud_backend():
    source = (ROOT / "api" / "main.py").read_text(encoding="utf-8")

    assert '@app.get("/api/health")' in source
    assert "get_cloud_backend_status" in source
    assert '"cloud"' in source


def test_postgres_check_script_loads_env_without_printing_secrets():
    source = (ROOT / "scripts" / "check_postgres.py").read_text(encoding="utf-8")

    assert "load_dotenv" in source
    assert "DATABASE_URL" in source
    assert "JWT_SECRET" in source
    assert "init_schema" in source
    assert "urlparse" in source
    assert "password" not in source.lower()
    assert "JWT_SECRET=" not in source


def test_launch_env_check_covers_https_login_cloud_and_voice_without_printing_secrets():
    source = (ROOT / "scripts" / "check_launch_env.py").read_text(encoding="utf-8")

    for expected in [
        "APP_PUBLIC_URL",
        "https",
        "DATABASE_URL",
        "JWT_SECRET",
        "COMPANION_ENV",
        "TEST_LOGIN_ENABLED",
        "TEST_LOGIN_WHITELIST",
        "SMS_ENABLED",
        "SMS_PROVIDER",
        "VOICE_PROVIDER",
        "DOUBAO_TTS_API_KEY",
        "DOUBAO_ASR_API_KEY",
        "AUDIO_STORAGE_PROVIDER=tos",
    ]:
        assert expected in source

    assert "load_dotenv" in source
    assert "your-api-key" not in source
    assert "print(os.getenv" not in source
    assert "JWT_SECRET=" not in source


def test_env_example_and_deployment_doc_cover_launch_cloud_contract():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "ecs-deployment.md").read_text(encoding="utf-8")

    assert "APP_PUBLIC_URL=https://your-domain.example" in env_example
    assert "COMPANION_ENV=production" in env_example
    assert "TEST_LOGIN_ENABLED=false" in env_example
    assert "TEST_LOGIN_CODE=123456" in env_example
    assert "TEST_LOGIN_WHITELIST=" in env_example
    assert "SMS_PROVIDER=none" in env_example
    assert "SMS_ENABLED=false" in env_example
    assert "DATABASE_URL=postgresql://" in env_example
    assert "JWT_SECRET=" in env_example
    assert "NEXT_PUBLIC_COMPANION_API_URL=" in env_example

    assert "APP_PUBLIC_URL=https://" in doc
    assert "COMPANION_ENV=production" in doc
    assert "NEXT_PUBLIC_COMPANION_API_URL=" in doc
    assert "python3 scripts/check_launch_env.py" in doc
    assert "getUserMedia" in doc
    assert "curl http://127.0.0.1:8000/api/health" in doc
    assert '"backend":"postgres"' in doc


def test_deploy_script_automates_safe_incremental_server_update():
    source = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    for expected in [
        "set -euo pipefail",
        'APP_DIR="/opt/companion"',
        'BRANCH="第一版"',
        'WEB_DIR="$APP_DIR/web"',
        'API_DIR="$APP_DIR/api"',
        'VENV_DIR="$APP_DIR/.venv"',
        'WEB_PM2_NAME="companion-web"',
        'API_PM2_NAME="companion-api"',
        'TEST_CMD="python3 -m pytest tests/test_chat_history_phase_c.py -v"',
        'OLD_COMMIT=$(git rev-parse HEAD)',
        "git fetch origin",
        'git pull origin "$BRANCH"',
        'NEW_COMMIT=$(git rev-parse HEAD)',
        "FORCE_WEB=0",
        "--force-web",
        "FRONTEND_CHANGE_PATTERN=",
        "web/|app/|pages/|components/|public/|styles/|src/",
        "next\\.config\\.(js|mjs|ts)",
        "package\\.json|package-lock\\.json|pnpm-lock\\.yaml|yarn\\.lock",
        "tailwind\\.config\\.(js|ts)",
        "postcss\\.config\\.(js|mjs)",
        "tsconfig\\.json",
        'CHANGED_FILES=$(git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT")',
        'echo "$CHANGED_FILES"',
        'grep -Eq "$FRONTEND_CHANGE_PATTERN"',
        "npm install",
        "npm run build",
        'pm2 restart "$WEB_PM2_NAME" --update-env',
        'source "$VENV_DIR/bin/activate"',
        'if [[ -f "$APP_DIR/requirements.txt" ]]; then',
        'pip install -r "$APP_DIR/requirements.txt"',
        'if [[ -f "$API_DIR/requirements.txt" ]]; then',
        'pip install -r "$API_DIR/requirements.txt"',
        "eval \"$TEST_CMD\"",
        'pm2 restart "$API_PM2_NAME" --update-env',
        "pm2 list",
    ]:
        assert expected in source

    forbidden = [
        "rm -rf",
        "drop database",
        "truncate table",
        "git reset --hard",
        ".env.local",
    ]
    lowered = source.lower()
    for text in forbidden:
        assert text not in lowered
    assert "grep -q '^web/'" not in source


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
