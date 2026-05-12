# 部署说明文档: 燃气轮机运行优化智能体

**版本**: 1.0
**日期**: 2026-05-11

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.12+ |
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

# 数据模式（当前仅支持 mock）
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

## 5. 常见问题

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
确保 Python 版本 >= 3.12：
```bash
python --version
```

### Q: npm install 报错
确保 Node.js 版本 >= 18：
```bash
node --version
```

---

## 6. Mock 数据说明

当前系统使用 Mock 数据运行，无需连接真实数据库或小模型 API。

- **SCADA 实时数据**: 29 项监测参数（每次请求随机生成，模拟实时变化）
- **能效指标**: 7 项效率指标由 SCADA 参数实时计算（热力学公式）
- **数据层位置**: `backend/src/data/mock_data.py`
- **替换路径**: 修改 `backend/src/data/connector.py` 中的函数实现即可切换到真实数据源，上层代码无需变动

---

## 7. LLM 接入指南

### 7.1 接入本地 Qwen 模型

使用 vLLM 或 Ollama 启动 OpenAI 兼容接口：

```bash
# vLLM 方式
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-72B-Instruct --port 8000

# Ollama 方式
ollama serve
ollama run qwen2.5:72b
```

### 7.2 配置连接

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

## 8. 功能页面清单

| 菜单 | 页面文件 | 功能说明 |
|------|----------|----------|
| 首页 | HomePage.vue | 状态卡片 + 燃机示意图 + 快捷操作 + 预警/日志 |
| 能效监测 | EfficiencyMonitor.vue | SCADA 组态图 + 7 项指标 + 趋势图 |
| 耗差分析 | LossAnalysis.vue | 损失柱状图 + 瀑布图 + 明细表 |
| 运营优化 | OperationOptimization.vue | 综合优化分析面板 |
| 对标分析 | BenchmarkOptimization.vue | 机组对标对比 |
| 预警管理 | WarningManagement.vue | 预警列表与详情 |
| 根因推理 | RootCauseDiagnosis.vue | 因果图 + 候选根因 + 证据链 + 诊断结论 |
| 数据字典 | DataDictionary.vue | 29 项参数 + 基准值模型 + 对标指标 |
| 模型与知识库 | ModelKnowledge.vue | 模型管理 + 知识库 + 向量库 + 因果图 |

---

*本文档随系统迭代持续更新。*
