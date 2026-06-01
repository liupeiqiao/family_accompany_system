# 服务器手动更新与运行手册

本文用于手动更新火山云 ECS 上的“亲情陪伴系统”正式运行环境。

## 当前服务器约定

- 项目目录：`/opt/companion`
- Git 分支：`第一版`
- 前端进程：`companion-web`
- 后端进程：`companion-api`
- 前端端口：`127.0.0.1:3000`
- 后端端口：`127.0.0.1:8000`
- 公网入口：Nginx `80/443`
- 不运行旧版 `app.py` Streamlit 原型

## 更新前检查

登录服务器后先进入项目目录：

```bash
cd /opt/companion
pwd
git status
pm2 list
```

确认 `pwd` 输出：

```text
/opt/companion
```

如果 `git status` 提示 `not a git repository`，说明当前不在项目目录，先重新执行：

```bash
cd /opt/companion
```

## 常规更新流程

适用于服务器没有本地代码改动的情况。

```bash
cd /opt/companion
git pull origin 第一版
```

安装或同步前端依赖：

```bash
npm --prefix web install
```

构建前端：

```bash
npm --prefix web run build
```

启用 Python 虚拟环境并运行关键测试：

```bash
source .venv/bin/activate
python3 -m pytest tests/test_chat_history_phase_c.py -v
```

重启 PM2 进程：

```bash
pm2 restart companion-api --update-env
pm2 restart companion-web --update-env
pm2 save
pm2 list
```

## 遇到服务器本地改动时

如果 `git pull` 出现类似提示：

```text
Your local changes to the following files would be overwritten by merge
```

先把服务器上的本地改动临时保存：

```bash
cd /opt/companion
git stash push -u -m "server-local-deploy-changes"
git pull origin 第一版
```

然后继续执行构建、测试和 PM2 重启：

```bash
npm --prefix web install
npm --prefix web run build

source .venv/bin/activate
python3 -m pytest tests/test_chat_history_phase_c.py -v

pm2 restart companion-api --update-env
pm2 restart companion-web --update-env
pm2 save
pm2 list
```

如果只想暂存指定文件，也可以使用：

```bash
git stash push -u -m "server-local-deploy-changes" -- web/package.json web/package-lock.json web/next-env.d.ts api.json
```

## 更新后健康检查

检查 PM2：

```bash
pm2 list
pm2 logs companion-api --lines 50
pm2 logs companion-web --lines 50
```

检查后端接口：

```bash
curl -I http://127.0.0.1:8000/docs
```

检查前端：

```bash
curl -I http://127.0.0.1:3000
```

检查 Nginx 公网入口：

```bash
curl -I http://115.190.119.178
```

如果已绑定域名，把 IP 换成域名。

## 功能验收清单

每次更新后至少检查：

- 登录页可打开
- 验证码登录可用
- 家庭空间可读取
- 家庭资料可保存
- 记录库可看到已保存资料
- 老人端聊天可返回 DeepSeek 回复
- 开启语音回复后，音频可以播放
- 声音复刻页面可查询音色状态
- PM2 中 `companion-api` 和 `companion-web` 都是 `online`

## 常见问题

### `git pull` 提示不是 Git 仓库

原因：当前目录不是 `/opt/companion`。

处理：

```bash
cd /opt/companion
git status
```

### `git pull` 被本地改动阻止

原因：服务器上改过文件，Git 担心远端更新覆盖这些改动。

处理：

```bash
git stash push -u -m "server-local-deploy-changes"
git pull origin 第一版
```

### 前端接口变成 `/api/api/...`

检查 `/opt/companion/.env`：

```bash
grep NEXT_PUBLIC_COMPANION_API_URL .env
```

服务器 Nginx 反代模式下应配置为空值：

```env
NEXT_PUBLIC_COMPANION_API_URL=
```

修改后重新构建并重启前端：

```bash
npm --prefix web run build
pm2 restart companion-web --update-env
pm2 save
```

### 后端返回 401

通常是浏览器未登录或 token 失效。重新登录后再试。

### 智能解析或聊天只返回兜底回复

检查服务器 `.env` 是否包含 DeepSeek 配置：

```bash
grep DEEPSEEK_BASE_URL .env
grep DEEPSEEK_API_KEY .env
```

不要把真实密钥粘贴到文档或聊天里。

修改 `.env` 后重启后端：

```bash
pm2 restart companion-api --update-env
pm2 save
```

### 语音不播放

先检查后端日志：

```bash
pm2 logs companion-api --lines 100
```

再检查 `.env` 是否有豆包配置：

```bash
grep VOICE_PROVIDER .env
grep DOUBAO_TTS_RESOURCE_ID .env
grep DOUBAO_TTS_CLONE_RESOURCE_ID .env
```

修改后重启：

```bash
pm2 restart companion-api --update-env
pm2 save
```

## 回滚到上一个版本

先查看最近提交：

```bash
git log --oneline -5
```

临时回滚到上一个提交：

```bash
git reset --hard HEAD~1
npm --prefix web install
npm --prefix web run build
pm2 restart companion-api --update-env
pm2 restart companion-web --update-env
pm2 save
```

仅在明确需要回滚时使用 `git reset --hard`。它会丢弃服务器当前工作区改动。

## 推荐的完整更新命令

正常情况下直接复制这一组：

```bash
cd /opt/companion
git status
git pull origin 第一版
npm --prefix web install
npm --prefix web run build
source .venv/bin/activate
python3 -m pytest tests/test_chat_history_phase_c.py -v
pm2 restart companion-api --update-env
pm2 restart companion-web --update-env
pm2 save
pm2 list
curl -I http://127.0.0.1:8000/docs
curl -I http://127.0.0.1:3000
curl -I http://115.190.119.178
```
