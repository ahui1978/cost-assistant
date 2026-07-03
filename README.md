# 造价智能助手

> 基于 FastAPI + OpenAI Function Calling 的工程造价智能对话与指标查询系统

## 功能特性

### 智能对话
- 接入 OpenAI 兼容接口（DeepSeek、通义千问、文心一言等）
- 支持流式输出（SSE）和非流式响应
- 温度调节（0~2）控制输出创造性
- 模拟模式（无 API Key 时可降级使用）

### 工具调用（Function Calling）
AI 对话中可自动调用以下工具获取真实数据：

| 工具 | 说明 | 数据来源 |
|------|------|----------|
| `query_pipeline_indicator` | 管线迁改预算指标查询 | 管线切改指标成果.xlsx |
| `query_cost_index` | 建筑造价指标查询 | 内置指标库 |

**管线迁改指标**覆盖六大专业：
- 电力（electric）
- 通信（communication）
- 燃气（gas）
- 给水（water）
- 排水（drainage）
- 热力（thermal）
- 通用工程、换算系数、费用取费标准

**造价指标**包含：
- 各类建筑单方造价（住宅/办公楼/商业/学校/医院/厂房）
- 费用构成比例（人工/材料/机械/管理/利润）
- 地区调价系数

### 功能页面

| 页面 | 说明 |
|------|------|
| [chat.html](chat.html) | 智能对话（支持工具调用状态展示） |
| [boq.html](boq.html) | 工程量清单编制 |
| [audit.html](audit.html) | 造价审核 |
| [dashboard.html](dashboard.html) | 造价指标看板 |
| [pipeline.html](pipeline.html) | 管线迁改指标查询 |

## 技术架构

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   前端页面   │────▶│  FastAPI 后端 │────▶│  OpenAI API  │
│  (HTML/JS)  │     │  (server.py) │     │  (DeepSeek)  │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  工具函数层   │
                    │  (tools.py)  │
                    └──────────────┘
                           │
                    ┌──────┴───────┐
                    ▼              ▼
              ┌──────────┐  ┌──────────┐
              │ 管线指标  │  │ 造价指标  │
              │ JSON数据  │  │ 内置数据  │
              └──────────┘  └──────────┘
```

### 关键设计
- **API Key 安全**：密钥仅存在服务端 `.env` 文件，前端不接触敏感信息
- **Function Calling**：大模型自主判断是否需要查数据，多轮调用循环（最多5轮）
- **流式工具调用**：前端实时展示「查询中 → 查询完成 → 生成回答」全过程

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 配置：

```env
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=deepseek-chat
SYSTEM_PROMPT=你是一位资深的工程造价专家...
```

### 3. 启动服务

```bash
python server.py
```

### 4. 访问应用

打开浏览器访问 http://localhost:8080

## 项目结构

```
cost-assistant/
├── server.py              # FastAPI 后端服务（API代理 + 工具调用 + 静态托管）
├── tools.py               # 工具函数定义与实现（Function Calling）
├── .env.example           # 环境变量模板
├── .env                   # 环境变量（需自行创建，不提交到 Git）
├── requirements.txt       # Python 依赖
├── .gitignore
│
├── chat.html              # 智能对话页面
├── boq.html               # 工程量清单页面
├── audit.html             # 造价审核页面
├── dashboard.html         # 造价指标看板页面
├── pipeline.html          # 管线迁改指标页面
├── index.html             # 首页导航
│
└── assets/
    ├── css/
    │   └── common.css     # 公共样式
    ├── js/
    │   ├── common.js      # 公共脚本
    │   └── pipeline-data.js  # 管线迁改结构化数据
    └── pipeline_raw.json  # 管线迁改原始数据
```

## 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_BASE_URL` | API 基础地址 | `https://api.deepseek.com/v1` |
| `OPENAI_API_KEY` | API 密钥 | `sk-xxxxx` |
| `OPENAI_MODEL` | 模型名称 | `deepseek-chat` |
| `SYSTEM_PROMPT` | 系统提示词（可选） | `你是一位资深的工程造价专家...` |
| `PORT` | 服务端口（默认 8080） | `8080` |

## 支持的 OpenAI 兼容接口

| 平台 | Base URL | 推荐模型 |
|------|----------|----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 文心一言 | `https://aip.baidubce.com/rpc/2.0/ai_custom/v1` | `ernie-bot-4` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

## 技术栈

- **后端**：Python 3.10+ / FastAPI / Uvicorn / httpx / python-dotenv
- **前端**：原生 HTML / CSS / JavaScript（无框架依赖）
- **AI**：OpenAI Compatible API / Function Calling
- **图标**：Lucide Icons

## License

MIT
