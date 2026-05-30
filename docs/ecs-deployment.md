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
DATABASE_URL=postgresql://admin:替换为真实口令@localhost:5432/companion
JWT_SECRET=替换为32位以上随机字符串
DEEPSEEK_API_KEY=替换为真实DeepSeekKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
VOICE_PROVIDER=doubao
DOUBAO_TTS_API_KEY=替换为真实豆包Key
DOUBAO_TTS_DEFAULT_VOICE_TYPE=zh_female_vv_uranus_bigtts
DOUBAO_TTS_RESOURCE_ID=seed-tts-2.0
DOUBAO_TTS_CLONE_RESOURCE_ID=seed-icl-2.0
```

正式上线前不要继续使用已经暴露过的数据库口令和 JWT 配置。

## 检查 PostgreSQL

```bash
python3 scripts/check_postgres.py
```

该脚本会加载 `.env`、连接 PostgreSQL、执行 schema 初始化，并确认 `productization/postgres_schema.sql` 可应用。

## PM2 启动

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 status
pm2 logs family-companion-api
pm2 logs family-companion-web
```

PM2 会启动两个进程：

- `family-companion-api`：`uvicorn api.main:app --host 127.0.0.1 --port 8000`
- `family-companion-web`：`npm run start -- --hostname 127.0.0.1 --port 3000`

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

## 验证

```bash
curl -I http://127.0.0.1:3000
curl -I http://127.0.0.1:8000/docs
curl -I http://服务器公网IP
```

浏览器访问：

```text
http://服务器公网IP
```

## 常见问题

- 如果页面能打开但 API 失败，先看 `pm2 logs family-companion-api`。
- 如果公网打不开，检查火山引擎安全组是否放行 80 端口。
- 如果数据库连接失败，确认应用和 PostgreSQL 同机时 `DATABASE_URL` 使用 `localhost`。
- 如果要使用域名和 HTTPS，先完成域名解析和备案，再扩展 Nginx 配置。
