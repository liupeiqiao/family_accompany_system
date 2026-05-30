# 云服务部署与生产化架构设计

## 当前状态

| 已完成 | 模式 | 待迁移到 |
|---|---|---|
| 声音克隆（豆包 V3 voice_clone） | 真实 API | 不需要改 |
| TTS 语音合成（豆包 SSE） | 真实 API | 不需要改 |
| 所有 CRUD API | InMemoryCloudRepository（重启丢数据） | PostgreSQL |
| 用户身份 | `X-User-Id: demo-user` 占位 | JWT 手机号登录 |
| 前后端启动 | 本地 `start.bat` 双击 | Docker Compose 一键部署 |
| 声音样本/生成语音 | 未存储（TTS 直接返回 base64） | TOS 对象存储 |

## 目标

1. 用火山引擎技术栈替代 InMemory 原型，实现数据持久化（ECS 自建 PostgreSQL）
2. 实现手机号 + 短信验证码注册登录（JWT），测试期验证码固定 000000
3. 将 FastAPI + Next.js + PostgreSQL + Nginx 通过 Docker Compose 部署到火山引擎 ECS
4. 现有业务逻辑（engine/、handlers.py、前端页面）尽量不动

## 非目标

1. 不做微信/支付宝等第三方登录（首版用手机号）
2. 不做集群/负载均衡（单机 Docker Compose 足够）
3. 不做 RLS（应用层校验替代）
4. 不做 CI/CD 自动部署（手动 git pull + docker compose up -d --build）
5. 第一阶段不买独立 RDS（ECS 自建 PostgreSQL；用户量上来再迁）

## 总体架构

```text
┌──────────────────────────────────────────────┐
│              火山引擎 ECS (2C4G)              │
│                                              │
│  ┌──────────┐    ┌──────────────┐           │
│  │  Nginx   │───→│  Next.js     │           │
│  │  :80     │    │  :3000       │           │
│  └────┬─────┘    └──────────────┘           │
│       │                                      │
│       │ proxy /api/*                         │
│       ▼                                      │
│  ┌──────────┐    ┌──────────────┐           │
│  │  FastAPI │───→│  PostgreSQL  │           │
│  │  :8000   │    │  :5432       │           │
│  └────┬─────┘    │  (Docker)    │           │
│       │           └──────────────┘           │
│       │                                      │
└───────┼──────────────────────────────────────┘
        │
   ┌────┴──────────┐
   │  TOS 对象存储  │  ← 火山引擎托管服务
   └───────────────┘
```

- **ECS 2C4G**：上海区域（cn-shanghai），按量付费约 ¥80-120/月
- **Nginx**：前端静态文件 + 反向代理 `/api/*` 到 FastAPI
- **Next.js**：服务端渲染 web 应用
- **FastAPI**：业务编排，SQLAlchemy + asyncpg 直连 PostgreSQL
- **PostgreSQL 16**：Docker 容器，ECS 本地 volume 持久化
- **TOS**：火山引擎对象存储，声音样本 + 生成语音文件，私有 bucket + 预签名 URL

### 为什么先用 ECS 自建 PostgreSQL 而不是买 RDS

| | ECS 自建 PostgreSQL | 独立 RDS PostgreSQL |
|---|---|---|
| 月成本 | ¥0（含在 ECS 里） | ~¥0.3/小时 ≈ ¥216/月 |
| 备份 | 需要自己配 pg_dump + TOS 备份脚本 | 自动备份 |
| 运维 | 需要自己升级、打补丁 | 托管 |
| 迁移成本 | 以后迁 RDS 只改一个连接串 | — |
| 适用阶段 | 首版 1-3 个家庭使用 | 用户量上来后 |

首版流量极低（每天几个家庭聊天），ECS 2C4G 跑 Nginx + Next.js + FastAPI + PostgreSQL 一个 Docker Compose 完全够用。

## 认证方案

### 用户表

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       VARCHAR(20) UNIQUE NOT NULL,
    nickname    VARCHAR(64) DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT now(),
    last_login  TIMESTAMPTZ
);
```

### API

| 接口 | 说明 |
|---|---|
| `POST /api/auth/send-code` | `{phone}` → 火山引擎短信发验证码，验证码存入 DB 5 分钟有效 |
| `POST /api/auth/verify` | `{phone, code}` → 验证码正确则返回 JWT，新用户自动注册 |

### 测试模式

首次部署时不接入短信，验证码固定 `000000`。代码里用一个开关控制：

```python
SMS_TEST_MODE = os.getenv("SMS_ACCESS_KEY") is None

if SMS_TEST_MODE:
    code = "000000"  # 任何手机号都接受 000000
else:
    code = generate_and_send_sms(phone)
```

### JWT 中间件

```python
from fastapi import Depends, Header, HTTPException
import jwt

def current_user(x_token: str = Header(alias="X-User-Token")) -> str:
    try:
        payload = jwt.decode(x_token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
```

之前所有 `X-User-Id: demo-user` → 替换为 `X-User-Token: <jwt>`。前端登录后 token 存 localStorage，每次请求由 `withUser()` 自动附加。

## 数据库（PostgreSQL 16）

### 完整表清单

```sql
-- 认证
users (id, phone, nickname, created_at, last_login)
sms_codes (id, phone, code, expires_at, used)

-- 家庭空间
families (id, name, created_by, created_at)
family_memberships (id, family_id, user_id, role, invited_at)

-- 业务数据（所有表带 family_id + created_by + updated_by）
elders (id, family_id, full_name, gender, personality, preferences, habits,
        health_notes, speech_traits, life_experiences, important_memories,
        notes, created_by, updated_by, created_at, updated_at)

family_profiles (id, family_id, name, gender, relation, personality,
                 preferences, habits, notes, relations,
                 created_by, updated_by, created_at, updated_at)

personas (id, family_id, role_label, relation, appellation, personality,
          speech_style, comfort_style, mood_preference, topic_affinity,
          sensitivity_map, created_by, updated_by, created_at, updated_at)

memories (id, family_id, content, memory_type, subject, family_members,
          emotion_tags, topic_tags, intimacy_weight,
          created_by, updated_by, created_at, updated_at)

-- 声音
voice_profiles (id, family_id, display_name, provider, provider_voice_id,
                status, consent_confirmed, sample_source, sample_ids,
                demo_audio_url, created_by, created_at)

voice_samples (id, family_id, storage_path, bucket, sample_source, status,
               voice_profile_id, created_by, created_at)

-- 聊天
chat_sessions (id, family_id, elder_id, created_at)
chat_messages (id, session_id, role, text, audio_storage_path, tts_provider, created_at)
```

### 索引

```sql
-- 权限查询
CREATE INDEX idx_family_memberships_user ON family_memberships(user_id);
CREATE INDEX idx_family_memberships_family ON family_memberships(family_id);

-- 家庭数据隔离（每条业务表都要）
CREATE INDEX idx_elders_family ON elders(family_id);
CREATE INDEX idx_family_profiles_family ON family_profiles(family_id);
CREATE INDEX idx_personas_family ON personas(family_id);
CREATE INDEX idx_memories_family ON memories(family_id);
CREATE INDEX idx_voice_profiles_family ON voice_profiles(family_id);
CREATE INDEX idx_voice_samples_family ON voice_samples(family_id);

-- 聊天查询
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
```

### 权限隔离（应用层）

不再依赖 RLS，在每个 repository 方法入口校验：

```python
def list_memories(self, *, family_id: str, user_id: str) -> list[dict]:
    self._require_member(family_id, user_id)  # 校验用户是否属于该家庭
    return self._query("SELECT * FROM memories WHERE family_id = ?", family_id)
```

## 对象存储（TOS）

### Bucket 设计

```
voice-samples/{family_id}/{user_id}/{sample_id}.{ext}
generated-audio/{family_id}/{chat_session_id}/{message_id}.mp3
```

### 费用

| 计费项 | 单价 |
|---|---|
| 标准存储 | ¥0.1/GiB/月 |
| 外网下行流量 | ¥0.5/GB |
|读写请求| ¥0.01/万次 |

前期声音样本和对话音频加起来每个月不会超过 1GB，约 ¥0.1-0.5/月。

### 预签名 URL

后端通过 TOS Python SDK 生成预签名 URL（5 分钟有效），前端直接上传/下载到 TOS，不经过 FastAPI 中转：

```python
from tos import TosClient

client = TosClient(endpoint, access_key, secret_key)
upload_url = client.pre_signed_url(
    bucket="companion",
    key=f"voice-samples/{family_id}/{user_id}/{sample_id}.wav",
    method="PUT",
    expires=300,
)
```

## CloudRepository 迁移

### 现状

```python
# cloud_repository.py
def get_cloud_repository() -> CloudRepository:
    config = SupabaseConfig.from_env()
    return SupabaseCloudRepository(config) if config else InMemoryCloudRepository()
```

### 迁移后

```python
def get_cloud_repository() -> CloudRepository:
    return PostgresCloudRepository(db_pool, tos_client)
```

`PostgresCloudRepository` 实现 `CloudRepository` 协议——数据层 asyncpg → PostgreSQL，文件层 TOS SDK → 预签名 URL。`CloudRepository` 方法签名不动，handlers.py 零改动。

## Docker 部署

### docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: companion
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

  backend:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db]
    restart: always

  frontend:
    build: ./web
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_COMPANION_API_URL=/api
    depends_on: [backend]
    restart: always

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on: [backend, frontend]
    restart: always

volumes:
  pgdata:
```

### 部署流程

```bash
# 1. 在 ECS 上装 Docker + Docker Compose（CentOS/Ubuntu 都有官方脚本）
# 2. git clone <仓库地址>
# 3. 把 .env 放到项目根目录
# 4. docker compose up -d
```

### 更新流程

```bash
git pull
docker compose up -d --build
```

### PostgreSQL 备份

```bash
# 定期备份到 TOS（crontab 每天凌晨执行）
docker compose exec db pg_dump -U admin companion | gzip > backup.sql.gz
# 上传到 TOS
```

## 资源成本汇总

| 资源 | 首年月费 |
|---|---|
| ECS 2C4G 上海 | ¥80-120 |
| 独立 RDS | **先用 ECS 自建，¥0** |
| TOS 对象存储 | ¥0.1-1 |
| 豆包 TTS + 克隆 | 按量计费，前期 < ¥20 |
| 短信验证码 | **测试模式，¥0** |
| DeepSeek API | 按量，前期 < ¥10 |
| **合计** | **约 ¥100-150/月** |

等用户量上来（10+ 家庭，日均 100 条聊天），再考虑：
- 升级 ECS 到 4C8G
- ECS PostgreSQL 迁移到独立 RDS
- 接入真实短信验证码

## 实施阶段

### 阶段 A：认证模块（1-2 天）

1. 写 `productization/auth.py`（send-code / verify / JWT 中间件）
2. 写 `api/auth.py`（两个路由：send-code、verify）
3. 写 `web/src/lib/auth.ts`（前端登录/注册页面，token 管理）
4. 修改 handlers.py：`X-User-Id: demo-user` → `X-User-Token: <jwt>`
5. 修改 `web/src/lib/backend-api.ts`：`withUser()` 附加 token
6. **测试模式**：任意手机号 + 000000 登录

### 阶段 B：PostgresCloudRepository（2-3 天）

1. 建立 PostgreSQL 表（init SQL 脚本）
2. 写 `productization/postgres_repository.py`（实现 CloudRepository 协议）
3. 数据层用 `asyncpg`（异步连接池，不阻塞 FastAPI event loop）
4. 切换 `get_cloud_repository()`：返回 PostgresCloudRepository
5. 数据迁移脚本（如果 InMemory 里已有测试数据）

### 阶段 C：TOS 接入（1 天）

1. 创建 TOS bucket（`voice-samples`、`generated-audio`，私有读写）
2. 写 `productization/tos_client.py`（上传/下载预签名 URL 生成）
3. 修改 voice 流程：音频保存到 TOS，数据库存 storage_path

### 阶段 D：Docker + ECS 部署（1 天）

1. 写 Dockerfile（后端 × 1，前端 × 1）
2. 写 `docker-compose.yml` + `nginx.conf`
3. 购买火山引擎 ECS 2C4G（上海）
4. `docker compose up -d`

### 阶段 E：域名 + HTTPS（1 天编排，1-3 周备案等待）

1. 购买域名 + 提交 ICP 备案（备案期间用 IP:port 访问）
2. Nginx 配 Let's Encrypt HTTPS 自动续期

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| ECS 成本 ¥80-120/月 | 足够支撑首版，后续按需扩容 |
| PostgreSQL 数据丢失 | cron + pg_dump 定期备份到 TOS |
| 短信未接、无法登录 | 测试模式兜底（000000），接短信前先确认模板审核通过 |
| ICP 备案周期长（1-3 周） | 先 IP:port 访问；备案和开发并行 |
| Docker 学习成本 | docker-compose.yml 已经写好，日常只需要 up/down/restart |
| `.env` 泄露 | gitignore 已配置，生产服务器手动放文件 |

## 待后续确认

1. 短信模板审核（火山引擎消息产品，备案域名下来后申请）
2. TOS bucket 权限策略（私有 + 后端签名 URL，前端直传）
3. PostgreSQL 备份策略（pg_dump 频率、TOS 上传脚本）
4. 是否需要 Redis（验证码缓存；首版可存 PostgreSQL）
