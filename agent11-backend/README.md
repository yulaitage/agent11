# AGENT 11 Backend

基于 Claude Code Harness 框架的智能基础设施管理 AI Agent 后端。

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      GAN Harness 架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Generator (Agent Generator)                  │    │
│  │  - LangGraph-based Agent                                  │    │
│  │  - 5 Skills: Query, Troubleshoot, Prediction, Report     │    │
│  │  - Memory Integration                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Evaluator (Eval Harness)                     │    │
│  │  - Rubric Scoring                                         │    │
│  │  - Test Case Management                                   │    │
│  │  - Regression Testing                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Loop Operator (Continuous Optimization)      │    │
│  │  - Metrics Collection                                     │    │
│  │  - Trend Analysis                                        │    │
│  │  - Auto Optimization                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Autonomous Loops                             │    │
│  │  - Skill Monitor                                         │    │
│  │  - Knowledge Updater                                      │    │
│  │  - Memory Optimizer                                       │    │
│  │  - Self Healing                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Memory Palace (Structured Memory)            │    │
│  │  - Wings: infra, convers, learning, user, meta          │    │
│  │  - Rooms: devices, patterns, episodes, preferences        │    │
│  │  - Tunnels: Cross-room queries                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Observability                               │    │
│  │  - Prometheus Metrics                                     │    │
│  │  - Structured Logging                                     │    │
│  │  - Health Checks                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

- **Framework**: FastAPI 0.110+
- **Agent**: LangGraph (工具调用 Agent)
- **LLM**: Llama/LM Studio (OpenAI-compatible API)
- **Database**: MongoDB + ChromaDB
- **Task Scheduling**: APScheduler
- **Metrics**: Prometheus

## 快速开始

### 1. 安装依赖

```bash
cd agent11-backend
pip install -e .
```

### 2. 配置

创建 `.env` 文件：

```env
MONGODB_URL=mongodb://gpu.cioic.com:27017
MONGODB_DATABASE=govChat
CHROMADB_PATH=./data/chromadb

# LLM - LM Studio
LLM_PROVIDER=lmstudio
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=llama-3.2-3b-instruct
LLM_TEMPERATURE=0.7
LLM_TIMEOUT=120
```

### 3. 启动

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. 测试对话

```bash
curl -X POST http://localhost:8000/api/chats \
  -H "Content-Type: application/json" \
  -d '{"title": "测试对话"}'

curl -X POST http://localhost:8000/api/chats/{chat_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "55区域有哪些故障路灯？", "skill": "query"}'
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/chats` | GET | 列出聊天 |
| `/api/chats` | POST | 创建聊天 |
| `/api/chats/{id}/messages` | POST | 发送消息 |
| `/api/knowledge` | GET | 搜索知识库 |
| `/api/memory/context` | GET | 获取记忆上下文 |
| `/api/llm/config` | GET/PUT | LLM 配置 |
| `/api/observability/metrics` | GET | Prometheus 指标 |
| `/api/health` | GET | 健康检查 |

## 5 个技能

1. **Query** - 自然语言数据查询
2. **Troubleshoot** - 故障诊断
3. **Prediction** - 故障/能耗预测
4. **Maintenance Report** - 周期性报告
5. **Flexible Report** - 灵活报告

## License

MIT
