#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/companion"
BRANCH="第一版"
WEB_DIR="$APP_DIR/web"
API_DIR="$APP_DIR/api"
VENV_DIR="$APP_DIR/.venv"
WEB_PM2_NAME="companion-web"
API_PM2_NAME="companion-api"
TEST_CMD="python3 -m pytest tests/test_chat_history_phase_c.py -v"
FRONTEND_CHANGE_PATTERN='^(web/|app/|pages/|components/|public/|styles/|src/|next\.config\.(js|mjs|ts)|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|tailwind\.config\.(js|ts)|postcss\.config\.(js|mjs)|tsconfig\.json)'
FORCE_WEB=0

for arg in "$@"; do
  case "$arg" in
    --force-web)
      FORCE_WEB=1
      ;;
    *)
      echo "错误：未知参数：$arg" >&2
      echo "用法：$0 [--force-web]" >&2
      exit 1
      ;;
  esac
done

log() {
  echo
  echo "==> $1"
}

require_path() {
  local path="$1"
  local message="$2"
  if [[ ! -e "$path" ]]; then
    echo "错误：$message：$path" >&2
    exit 1
  fi
}

log "[1/6] 进入项目目录"
require_path "$APP_DIR" "项目目录不存在"
cd "$APP_DIR"
echo "当前目录：$(pwd)"
require_path "$APP_DIR/.git" "当前目录不是 Git 仓库"
require_path "$WEB_DIR" "前端目录不存在"
require_path "$API_DIR" "后端目录不存在"
require_path "$VENV_DIR/bin/activate" "Python 虚拟环境不存在，请确认 VENV_DIR 配置"

OLD_COMMIT=$(git rev-parse HEAD)
echo "更新前 commit：$OLD_COMMIT"

log "[2/6] 拉取最新代码"
git fetch origin
git pull origin "$BRANCH"
NEW_COMMIT=$(git rev-parse HEAD)
echo "更新后 commit：$NEW_COMMIT"

if [[ "$OLD_COMMIT" == "$NEW_COMMIT" ]]; then
  echo "代码没有变化。"
else
  echo "代码已更新：$OLD_COMMIT -> $NEW_COMMIT"
fi

log "[3/6] 检查前端是否变化"
WEB_CHANGED=0
CHANGED_FILES=""
if [[ "$OLD_COMMIT" != "$NEW_COMMIT" ]]; then
  CHANGED_FILES=$(git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT")
  echo "本次变更文件："
  echo "$CHANGED_FILES"
  if echo "$CHANGED_FILES" | grep -Eq "$FRONTEND_CHANGE_PATTERN"; then
    WEB_CHANGED=1
  fi
else
  echo "本次变更文件："
  echo "$CHANGED_FILES"
fi

if [[ "$FORCE_WEB" -eq 1 ]]; then
  echo "检测到 --force-web，强制重建前端。"
  WEB_CHANGED=1
fi

if [[ "$WEB_CHANGED" -eq 1 ]]; then
  echo "检测到前端相关变化或强制重建请求。"
else
  echo "前端未变化，跳过 npm install / build / restart"
fi

log "[4/6] 部署前端"
if [[ "$WEB_CHANGED" -eq 1 ]]; then
  cd "$WEB_DIR"
  npm install
  npm run build
  pm2 restart "$WEB_PM2_NAME" --update-env
else
  echo "前端无变化，本步骤跳过。"
fi

log "[5/6] 部署后端"
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  echo "检测到 requirements.txt，安装项目 Python 依赖。"
  pip install -r "$APP_DIR/requirements.txt"
else
  echo "未检测到 requirements.txt，跳过项目 Python 依赖安装。"
fi

if [[ -f "$API_DIR/requirements.txt" ]]; then
  echo "检测到 api/requirements.txt，安装后端 API 依赖。"
  pip install -r "$API_DIR/requirements.txt"
else
  echo "未检测到 api/requirements.txt，跳过 API 专属依赖安装。"
fi

echo "执行测试：$TEST_CMD"
eval "$TEST_CMD"
pm2 restart "$API_PM2_NAME" --update-env

log "[6/6] 检查 PM2 状态"
pm2 status "$WEB_PM2_NAME"
pm2 status "$API_PM2_NAME"
pm2 list

echo
echo "部署完成。"
