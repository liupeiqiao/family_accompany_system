# ECS 部署说明

本文用于把“亲情陪伴系统”部署到火山引擎 ECS。目标是直接部署最新 Web 应用（Next.js/React + FastAPI），不要部署旧版 Streamlit。

## 前置条件

- Ubuntu 22.04
- 已安装 PostgreSQL，并已创建数据库 `companion` 和用户 `admin`
- 已安装 Git、Python 3、Node.js、Nginx、PM2
- 服务器已配置 GitHub SSH Key
- 项目根目录 `.env` 只放在服务器，不提交到 Git

## 克隆代码

```bash
git clone -b 第一版 git@github.com:liupeiqiao/family_accompany_system.git companion
cd companion
```

如果 HTTPS clone 出现 `GnuTLS recv error (-110)`，继续使用 SSH clone。

## 安装依赖

后端：

```bash
python3 -m pip install -r requirements.txt
```

前端：

```bash
cd web
npm install
npm run build
cd ..
```

## 配置环境变量

在项目根目录创建 `.env`：

```env
COMPANION_ENV=production
APP_PUBLIC_URL=https://your-domain.example
TEST_LOGIN_ENABLED=false
TEST_LOGIN_CODE=123456
TEST_LOGIN_WHITELIST=
SMS_PROVIDER=none
SMS_ENABLED=false
DATABASE_URL=postgresql://admin:替换为真实口令@localhost:5432/companion
JWT_SECRET=替换为32位以上随机字符串
NEXT_PUBLIC_COMPANION_API_URL=
DEEPSEEK_API_KEY=替换为真实DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
VOICE_PROVIDER=doubao
DOUBAO_TTS_API_KEY=替换为真实豆包Key
DOUBAO_TTS_DEFAULT_VOICE_TYPE=zh_female_vv_uranus_bigtts
DOUBAO_TTS_RESOURCE_ID=seed-tts-2.0
DOUBAO_TTS_CLONE_RESOURCE_ID=seed-icl-2.0

# 可选：火山引擎 TOS 对象存储，用于长期保存 AI 回复音频
# AUDIO_STORAGE_PROVIDER=tos
# TOS_ACCESS_KEY_ID=替换为TOS AccessKey
# TOS_SECRET_ACCESS_KEY=替换为TOS SecretKey
# TOS_ENDPOINT=https://tos-cn-beijing.volces.com
# TOS_REGION=cn-beijing
# TOS_BUCKET=替换为TOS Bucket名称
# TOS_PUBLIC_BASE_URL=https://替换为可访问的Bucket域名或CDN域名
# TOS_PREFIX=generated-audio
```

正式上线前不要继续使用已经暴露过的数据库口令和 JWT 配置。

内测环境如果还没有接真实短信服务，不要使用 `COMPANION_ENV=production`。请改为：

```env
COMPANION_ENV=staging
TEST_LOGIN_ENABLED=true
TEST_LOGIN_CODE=123456
TEST_LOGIN_WHITELIST=13800000000
SMS_PROVIDER=none
SMS_ENABLED=false
```

生产环境必须保持 `TEST_LOGIN_ENABLED=false`，并配置真实短信服务。未接真实短信服务时，生产环境验证码登录会被拒绝，这是为了避免固定验证码上线。

## 检查 PostgreSQL

```bash
python3 scripts/check_postgres.py
```

该脚本会加载 `.env`、连接 PostgreSQL、执行 schema 初始化，并确认 `productization/postgres_schema.sql` 可应用。

上线前再执行完整环境检查：

```bash
python3 scripts/check_launch_env.py
```

该脚本会检查 `APP_PUBLIC_URL` 是否使用 HTTPS、`DATABASE_URL`/`JWT_SECRET` 是否配置、登录策略是否安全、豆包 ASR/TTS 是否具备基础配置。浏览器 `getUserMedia` 在公网域名下要求 HTTPS，否则老人端录音不可用。

## TOS 对象存储

TOS 是火山引擎对象存储。当前系统的核心文字数据已经保存在 PostgreSQL 中，包括用户、家庭空间、老人档案、家人档案、家庭记忆、音色记录和对话文字历史。TOS 主要负责保存文件类数据，尤其是 AI 回复音频。

### 什么情况下必须配置 TOS

以下场景建议上线前配置 TOS：

- 需要“关闭通话后仍可重播历史 AI 回复音频”。
- 需要服务器重启、重新部署、迁移 ECS 后，历史音频仍然可访问。
- 后续要保存老人录音、家人音色样本或生成音频文件。
- 不希望音频文件只依赖 ECS 本地磁盘或临时 URL。

以下场景可以暂时不配置 TOS：

- 只验证登录、档案、记忆、音色元数据和文字对话持久化。
- 老人端语音回复只要求“当次播放”，不要求历史音频长期重播。
- 内测早期可以接受历史页面中只有文字记录稳定保留。

不配置 TOS 时，PostgreSQL 里的文字数据仍然会保留；但 AI 回复音频的长期可访问性不保证。

### TOS 配置项说明

```env
AUDIO_STORAGE_PROVIDER=tos
TOS_ACCESS_KEY_ID=替换为TOS AccessKey
TOS_SECRET_ACCESS_KEY=替换为TOS SecretKey
TOS_ENDPOINT=https://tos-cn-beijing.volces.com
TOS_REGION=cn-beijing
TOS_BUCKET=替换为TOS Bucket名称
TOS_PUBLIC_BASE_URL=https://替换为可访问的Bucket域名或CDN域名
TOS_PREFIX=generated-audio
```

- `AUDIO_STORAGE_PROVIDER=tos`：开启 TOS 音频存储。
- `TOS_ACCESS_KEY_ID` / `TOS_SECRET_ACCESS_KEY`：服务器访问 TOS 的密钥，只能放在服务器 `.env`，不要提交到 Git。
- `TOS_ENDPOINT`：TOS 服务地址，需和 Bucket 所在地域一致。
- `TOS_REGION`：Bucket 地域，例如 `cn-beijing`。
- `TOS_BUCKET`：用于保存生成音频的 Bucket。
- `TOS_PUBLIC_BASE_URL`：前端播放音频使用的访问域名，可以是 Bucket 外网域名或 CDN 域名。
- `TOS_PREFIX`：对象路径前缀，建议保持 `generated-audio`。

### Bucket 权限建议

内测阶段可以先使用可访问的 Bucket 域名或 CDN 域名，让前端能直接播放音频。后续如果要加强隐私，建议改为私有 Bucket + 后端签名 URL。

不要把 TOS AccessKey、SecretKey 写入前端环境变量。前端只需要拿后端返回的 `audio_url` 播放音频。

### 配置后如何验证

1. 修改服务器 `.env` 后重启后端：

```bash
pm2 restart companion-api --update-env
```

2. 在老人端完成一次语音对话。

3. 打开对话历史页面，确认 AI 回复旁边的重播按钮可以播放。

4. 重启服务后再次验证历史重播：

```bash
pm2 restart companion-api --update-env
pm2 restart companion-web --update-env
```

如果重启后历史文字还在，但重播失败，优先检查 TOS 配置、Bucket 访问权限和 `TOS_PUBLIC_BASE_URL`。

## PM2 启动

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 status
pm2 logs companion-api
pm2 logs companion-web
```

PM2 会启动两个进程：

- `companion-api`：`uvicorn api.main:app --host 127.0.0.1 --port 8000`
- `companion-web`：`npm run start -- --hostname 127.0.0.1 --port 3000`

更新代码后：

```bash
git pull
python3 -m pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
python3 scripts/check_postgres.py
pm2 restart ecosystem.config.js
```

## Nginx 配置

复制模板：

```bash
sudo cp deploy/nginx/family-companion.conf /etc/nginx/sites-available/family-companion.conf
sudo ln -sf /etc/nginx/sites-available/family-companion.conf /etc/nginx/sites-enabled/family-companion.conf
sudo nginx -t
sudo systemctl reload nginx
```

模板文件：`deploy/nginx/family-companion.conf`

路由规则：

- `/` 反向代理到 `127.0.0.1:3000`
- `/api/` 反向代理到 `127.0.0.1:8000`

如果通过域名给老人端使用，必须配置 HTTPS。未配置 HTTPS 时，浏览器会因为 `getUserMedia` 安全限制拦截麦克风权限，老人端录音无法正常使用。可以先用 Certbot 为 Nginx 申请证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
sudo nginx -t
sudo systemctl reload nginx
```

## 验证

```bash
curl -I http://127.0.0.1:3000
curl -I http://127.0.0.1:8000/docs
curl http://127.0.0.1:8000/api/health
curl -I http://服务器公网IP
```

`/api/health` 应返回持久化云端后端，例如：

```json
{"ok":true,"cloud":{"backend":"postgres","persistent":true,"configured":true}}
```

该结果只能证明数据库持久化正常，不能证明 TOS 音频存储已配置。TOS 是否生效，需要通过一次语音对话后的历史音频重播来验证。

浏览器访问：

```text
http://服务器公网IP
```

## 常见问题

- 如果页面能打开但 API 失败，先看 `pm2 logs companion-api`。
- 如果公网打不开，检查火山引擎安全组是否放行 80 端口。
- 如果数据库连接失败，确认应用和 PostgreSQL 同机时 `DATABASE_URL` 使用 `localhost`。
- 如果要使用域名和 HTTPS，先完成域名解析和备案，再扩展 Nginx 配置。
- 如果历史页面文字还在但音频无法重播，检查是否配置了 `AUDIO_STORAGE_PROVIDER=tos`、TOS Bucket 权限和 `TOS_PUBLIC_BASE_URL`。
