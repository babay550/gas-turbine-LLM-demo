# 部署说明文档: 燃气轮机运行优化智能体

**版本**: 1.1
**日期**: 2026-06-15

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| 包管理器 | pip (后端), npm (前端) |
| 操作系统 | Windows / Linux |
| LLM (可选) | Qwen / ChatGLM 等本地模型，需提供 OpenAI 兼容接口 |

---

## 2. 项目结构

```
gas-turbine-LLM-demo/
├── backend/                    # Python 后端 (FastAPI)
│   ├── requirements.txt
│   ├── .env.example            # 环境变量模板
│   └── src/
│       ├── api/                # REST API 路由 (7 个模块)
│       ├── agents/             # Agent 实现
│       ├── core/               # 调度器 + 触发引擎
│       ├── data/               # 数据连接器 + Mock 数据
│       └── tools/              # LangChain 工具封装
├── frontend/                   # Vue 3 前端
│   ├── package.json
│   ├── vite.config.ts          # 开发代理配置
│   └── src/
│       ├── api/                # Axios HTTP 客户端
│       ├── views/              # 9 个功能页面
│       ├── stores/             # 响应式状态管理
│       ├── types/              # TypeScript 类型定义
│       └── components/         # 布局 + 对话组件
└── docs/                       # PRD + 部署文档
```

---

## 3. 后端部署

### 3.1 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

核心依赖：
- fastapi, uvicorn — Web 框架和 ASGI 服务器
- langchain, langchain-openai — Agent 框架和 LLM 接入
- httpx — 异步 HTTP 客户端（模型联通测试）
- pandas, numpy — 数据处理
- pydantic — 配置管理
- apscheduler — 定时任务调度

### 3.2 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# LLM 配置（可选，不配置时 Agent 工具直调仍可用）
LLM_BASE_URL=http://localhost:8000/v1
LLM_API_KEY=empty
LLM_MODEL_NAME=qwen2.5-72b-instruct
LLM_TEMPERATURE=0.3

# 数据模式
DATA_MODE=mock
```

> LLM 不可用时系统自动降级：Agent 对话功能不可用，但仪表盘一键触发（能效/耗差/对标分析）和所有 API 端点正常工作。

### 3.3 启动后端

```bash
cd backend
uvicorn src.api.main:app --reload --port 8000
```

验证启动成功：
```bash
curl http://localhost:8000/api/health
# 返回 {"status":"ok"}
```

### 3.4 API 端点一览

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/monitoring/realtime` | GET | 实时 SCADA 监测数据（29 项参数） |
| `/api/monitoring/efficiency-trend` | GET | 能效指标趋势 |
| `/api/analysis/efficiency` | POST | 执行能效分析（7 项指标 + 27 项 SCADA 值） |
| `/api/analysis/loss` | POST | 执行耗差分析 |
| `/api/analysis/benchmark` | POST | 执行对标分析 |
| `/api/analysis/decomposition` | POST | 逐级分解 |
| `/api/analysis/root-cause` | POST | 根因推理 |
| `/api/chat/message` | POST | Agent 对话 |
| `/api/chat/ws` | WebSocket | Agent 流式对话 |
| `/api/schedule/tasks` | GET/POST | 定时任务管理 |
| `/api/schedule/trigger` | POST | 手动触发任务 |
| `/api/schedule/logs` | GET | 执行日志 |
| `/api/warning/list` | GET | 预警列表 |
| `/api/warning/{id}` | GET | 预警详情 |
| `/api/dictionary/parameters` | GET | 监测参数定义 |
| `/api/dictionary/baselines` | GET | 基准值模型配置 |
| `/api/dictionary/benchmark-indicators` | GET | 对标指标 |
| `/api/knowledge/models` | GET/POST | 小模型接口管理 |
| `/api/knowledge/models/{id}/test` | POST | 模型联通测试 |
| `/api/knowledge/knowledge/maintenance` | GET/POST | 检维修知识库 |
| `/api/knowledge/knowledge/rules` | GET | 专家规则 |
| `/api/knowledge/knowledge/vector-sources` | GET/POST | 向量知识库接入 |
| `/api/knowledge/knowledge/vector-sources/{id}/test` | POST | 向量知识库联通测试 |
| `/api/knowledge/knowledge/causal-graph` | GET | 因果图 |
| `/api/auth/login` | POST | 登录获取 JWT（默认账号 admin/admin123） |
| `/api/auth/me` | GET | 当前登录用户信息 |
| `/api/historical/range` | GET | 时序数据时间范围 |
| `/api/historical/query` | GET | 时序数据查询 |
| `/api/historical/stats` | GET | 参数统计摘要 |
| `/api/analysis/historical-loss` | POST | 历史耗差分析（偏差分解，可选负荷率三区间） |
| `/api/analysis/qa` | POST | 数据问答（耗差+统计+知识库三源，LLM 作答） |
| `/api/analysis/qa/history` | GET/DELETE | 数据问答历史（按用户隔离，可清空） |
| `/api/data-import/upload` | POST | 时序数据文件上传（xlsx/csv） |

> **认证**：除 `/api/health`、`/api/auth/login` 外，所有端点需在请求头携带 `Authorization: Bearer <JWT>`。首次部署后用默认账号 `admin / admin123` 登录（**生产环境务必修改密码**，见 `/api/auth/me/password`）。

---

## 4. 前端部署

### 4.1 安装依赖

```bash
cd frontend
npm install
```

### 4.2 开发模式启动

```bash
npm run dev
```

默认访问 `http://localhost:5173`，Vite 自动代理 `/api` 请求到后端 `http://localhost:8000`。

代理配置在 `frontend/vite.config.ts`：
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

如果后端使用其他端口，修改 `target` 即可。

### 4.3 生产构建

```bash
npm run build
```

输出到 `frontend/dist/`，可部署到 Nginx 等 Web 服务器。

Nginx 配置示例：
```nginx
server {
    listen 80;
    server_name your-domain;

    # 允许大文件上传（数据字典 xlsx / 时序数据 / 知识库文档）
    client_max_body_size 100m;
    # 数据问答等含 LLM 调用的请求较慢，放宽代理读超时
    proxy_read_timeout 300s;

    root /path/to/gas-turbine-LLM-demo/frontend/dist;
    index index.html;

    # SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理到后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 5. Docker 部署（推荐）

适用于快速部署和容器化生产环境。项目已内置完整的 Docker 配置，一条命令即可启动前后端。

### 5.1 前置条件

| 项目 | 要求 |
|------|------|
| Docker | 20.10+ |
| Docker Compose | v2（docker compose 命令） |
| 磁盘空间 | ≥ 2 GB（镜像构建） |

### 5.2 目录结构

```
docker/
├── docker-compose.yml        # 编排文件
├── backend/
│   └── Dockerfile            # 后端镜像（Python 3.11-slim + pip）
└── frontend/
    ├── Dockerfile            # 前端镜像（Node 22 构建 + Nginx 运行）
    └── nginx.conf            # Nginx 反向代理配置
```

### 5.3 架构说明

| 容器 | 基础镜像 | 功能 | 端口映射 |
|------|----------|------|----------|
| `gas-turbine-backend` | python:3.11-slim | FastAPI 后端服务 | `8000:8000` |
| `gas-turbine-frontend` | nginx:alpine | 前端静态资源 + API 反向代理 | `18081:80` |

前端容器内的 Nginx 通过 Docker 网络（`gas-app-network`）将 `/api/` 请求代理到 `backend:8000`，外部只需访问前端端口即可。

### 5.4 快速启动

**1）准备环境变量**

```bash
# 在项目根目录下，确保后端 .env 文件存在
cp backend/.env.example backend/.env
# 根据需要编辑 LLM_BASE_URL 等配置
```

> **注意**：Docker 环境中如果 LLM 服务也在本地运行，`LLM_BASE_URL` 不能使用 `localhost`，需使用 `host.docker.internal`（Docker Desktop）或宿主机 IP。

```ini
# Windows / macOS (Docker Desktop)
LLM_BASE_URL=http://host.docker.internal:8000/v1

# Linux（使用宿主机实际 IP，如 192.168.1.100）
LLM_BASE_URL=http://192.168.1.100:8000/v1
```

**2）构建并启动**

```bash
# 在项目根目录执行
docker compose -f docker/docker-compose.yml up -d --build
```

首次执行会构建镜像，耗时约 2-5 分钟（取决于网络速度）。

**3）验证**

```bash
# 检查容器状态
docker compose -f docker/docker-compose.yml ps

# 健康检查
curl http://localhost:8000/api/health
# 返回 {"status":"ok"}
```

浏览器访问 `http://localhost:18081` 即可使用系统。

### 5.5 常用操作

```bash
# 查看日志
docker compose -f docker/docker-compose.yml logs -f

# 仅查看后端日志
docker compose -f docker/docker-compose.yml logs -f backend

# 重启服务
docker compose -f docker/docker-compose.yml restart

# 停止并删除容器
docker compose -f docker/docker-compose.yml down

# 停止并删除容器 + 镜像
docker compose -f docker/docker-compose.yml down --rmi all
```

### 5.6 数据持久化

docker-compose.yml 通过 volumes 挂载以下目录：

| 容器内路径 | 宿主机路径 | 说明 |
|------------|------------|------|
| `/app/data` | `backend/data` | 数据文件 |
| `/app/knowledge` | `backend/knowledge` | 知识库文件 |
| `/app/.env` | `backend/.env` | 环境变量配置 |

这些目录的内容在容器重建后不会丢失。

> **数据库**：`backend/data/gasturbine.db`（SQLite，WAL 模式）存储全部业务数据——时序数据（`tsd_time_series`）、参数字典、数据问答历史（`tsd_historical_qa_messages`，按用户隔离）、用户/组织等。表结构在容器启动时由 `init_db()` 自动创建并做在线迁移（如补 `user_id` 列），**无需手动建表**。

### 5.7 自定义端口

如需修改对外端口，编辑 `docker/docker-compose.yml` 中的 `ports` 映射：

```yaml
# 后端端口（默认 8000）
ports:
  - "9000:8000"    # 将宿主机 9000 映射到容器 8000

# 前端端口（默认 18081）
ports:
  - "80:80"        # 将宿主机 80 映射到容器 80
```

---

## 6. 常见问题

### Q: 端口 8000 被占用
```bash
# Windows: 查看占用进程
netstat -ano | findstr ":8000"
# 结束进程
taskkill /PID <PID> /F

# 或换端口启动
uvicorn src.api.main:app --reload --port 8001
# 同时修改 frontend/vite.config.ts 中的 proxy target
```

### Q: 后端启动报 LLM 连接错误
LLM 连接失败不影响系统运行。`BaseAgent.__init__` 会捕获异常并设置 `_llm_available = False`。此时：
- 仪表盘一键触发分析 → 正常（工具直调）
- Agent 对话功能 → 提示"LLM 服务暂不可用"
- 所有 REST API → 正常

### Q: 前端页面数据全部显示 0
确认后端已启动且前端代理配置正确：
1. 后端终端应显示 `Uvicorn running on http://127.0.0.1:8000`
2. 浏览器访问 `http://localhost:8000/api/health` 应返回 `{"status":"ok"}`
3. 如果后端端口不是 8000，需要同步修改 `frontend/vite.config.ts`

### Q: pip install 报错
确保 Python 版本 >= 3.11：
```bash
python --version
```

### Q: npm install 报错
确保 Node.js 版本 >= 18：
```bash
node --version
```

### Q: 耗差分析结果为空或提示「无 coalLossValue」
耗差分析依赖导入数据中的 `{因素}_coalLossValue` / `_optimalLossValue` 时序项（见 §7.2 数据契约）。确认上传的时序文件包含这些字段，且 parameter_key 命名与 `LOSS_HIERARCHY` 的因素名一致（如 `压气机效率_coalLossValue`）。因素缺值会自动跳过，不影响其他因素。

### Q: 数据问答报「timeout exceeded」
数据问答需执行耗差分析 + 知识库检索 + LLM 生成，耗时较长（前端已设 180s 超时）。若仍超时：①确认 LLM 服务可达（`.env` 的 `LLM_BASE_URL`）；②大数据量时段耗差分析较慢，缩小查询时段；③nginx `proxy_read_timeout` 已设 300s，无需改动。

---

## 7. 数据来源与耗差分析数据契约

### 7.1 数据来源

系统通过 SQLite（`backend/data/gasturbine.db`）持久化时序数据，经「数据导入」页面或 `/api/data-import/upload` 上传 xlsx/csv 导入；导入后即可驱动历史分析、耗差分析、数据问答等功能。

- **时序数据**：导入的真实运行数据（`tsd_time_series` 表）
- **耗差分析**：直接读取导入数据中**系统上报的已算好耗差值**做偏差分解，**不使用 mock**
- **能效/对标分析**：默认 mock 模式（`force_mock`），由 `backend/src/data/connector.py` 控制；接入真实数据源时修改 connector 实现即可，上层代码无需变动

### 7.2 耗差分析数据契约（部署关键）

耗差分析（`loss_analysis_tool`）沿「能耗偏差 → 燃机效率 / 余热锅炉效率 / 汽机效率 → 各下属因素」层级做偏差分解，依赖时序表中按命名约定上报的耗差值：

| 时序 parameter_key 后缀 | 含义 |
|------|------|
| `{name}_coalLossValue` | 对标基准耗差 (g/kWh) — 评估模式「对标基准」 |
| `{name}_optimalLossValue` | 对标最优耗差 (g/kWh) — 评估模式「对标最优」 |
| `{name}_value` | 运行过程值 |
| `{name}_referValue` | 基准参考值 |

其中 `{name}` ∈ {`能耗偏差`（总量）, `燃机效率`/`余热锅炉效率`/`汽机效率`（3 子系统）, 各因素}，因素归属见 `LOSS_HIERARCHY`（`backend/src/tools/loss_analysis_tool.py`）。

- **评估模式**：`coal`（对标基准，用 coalLossValue）/ `optimal`（对标最优，用 optimalLossValue），全程用对应值，二者不混用
- **聚合方式**（实时页）：`raw`=最新单点、`1d`=最近1天均值、`1w`=最近1周均值
- **负荷率三区间**（可选）：若时序含「负荷率」或「发电机有功功率」参数，自动按 <10% 舍去、10–60% 关注异常偏高、>60% 详细分析；无则整体分析
- 因素缺某模式的值时自动跳过（容错，不 mock）

---

## 8. LLM 接入指南

### 8.1 接入本地 Qwen 模型

使用 vLLM 或 Ollama 启动 OpenAI 兼容接口：

```bash
# vLLM 方式
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-72B-Instruct --port 8000

# Ollama 方式
ollama serve
ollama run qwen2.5:72b
```

### 8.2 配置连接

编辑 `backend/.env`：
```ini
LLM_BASE_URL=http://localhost:8000/v1    # vLLM
# 或
LLM_BASE_URL=http://localhost:11434/v1   # Ollama

LLM_API_KEY=empty
LLM_MODEL_NAME=Qwen2.5-72B-Instruct
```

重启后端即可生效。

---

## 9. 功能页面清单

| 菜单 | 页面文件 | 功能说明 |
|------|----------|----------|
| 首页 | HomePage.vue | 状态卡片 + 燃机示意图 + 快捷操作 + 预警/日志 |
| 能效监测 | EfficiencyMonitor.vue | SCADA 组态图 + 7 项指标 + 趋势图 |
| 耗差分析 | LossAnalysis.vue | 损失柱状图 + 瀑布图 + 明细表 |
| 运营优化 | OperationOptimization.vue | 综合优化分析面板 |
| 对标分析 | BenchmarkOptimization.vue | 机组对标对比 |
| 预警管理 | WarningManagement.vue | 预警列表与详情 |
| 根因推理 | RootCauseDiagnosis.vue | 因果图 + 候选根因 + 证据链 + 诊断结论 |
| 数据字典 | DataDictionary.vue | 监测项参数 + 基准值模型 + 对标指标 |
| 模型与知识库 | ModelKnowledge.vue | 模型管理 + 知识库 + 向量库 + 因果图 |

---

*本文档随系统迭代持续更新。*
