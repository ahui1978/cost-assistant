# -*- coding: utf-8 -*-
"""
造价智能助手 - 后端服务
功能：
  1. 托管前端静态页面
  2. 代理 OpenAI 兼容 API（API Key 由环境变量管理，前端不接触密钥）
  3. 支持流式 SSE 响应
  4. 支持 Function Calling 工具调用（管线迁改指标、造价指标）
"""
import os
import json
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
import httpx

from tools import TOOLS, execute_tool, get_pipeline_data, get_cost_index_data

# 加载 .env 文件中的环境变量
load_dotenv()

# ========== 配置 ==========
API_BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
API_MODEL = os.getenv("OPENAI_MODEL", "")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

# 前端静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".")

# 系统提示词前缀（告诉模型有哪些工具可用）
TOOL_SYSTEM_PROMPT = """
你有以下工具可以调用以获取准确的造价数据：

【工具1】query_pipeline_indicator - 查询管线迁改工程预算限额指标
参数：
- profession: 专业类别，可选 electric(电力)、communication(通信)、gas(燃气)、water(给水)、drainage(排水)、thermal(热力)、general(通用工程)、conversion(换算系数)、fee(费用取费标准)
- keyword: 搜索关键词（如管径、材料名称等），用于精准匹配

【工具2】query_cost_index - 查询建筑工程造价指标
参数：
- query_type: building_type(建筑单方造价)、cost_composition(费用构成)、region_factor(地区系数)
- keyword: 建筑类型关键词（仅 building_type 时使用）

调用规则：
1. 只在用户问题涉及具体数据查询时才调用工具，普通问答不需要
2. 管线迁改问题只查询用户明确提到的专业，不要把6个专业全查一遍
3. 如果用户问「DN300管道多少钱」且未指定专业，优先查询给水和排水，再根据需要补充
4. 每次最多调用2-3个工具，通过多轮对话逐步补充信息
5. 拿到工具结果后，基于数据用自然语言回答用户，不要原样返回JSON

请始终优先使用工具获取数据，而不是凭记忆回答。
"""

# ========== FastAPI 应用 ==========
app = FastAPI(title="造价智能助手后端")

# HTTP 客户端（带连接池）
client = httpx.AsyncClient(timeout=120.0)


@app.on_event("startup")
async def startup():
    """启动时加载数据并打印配置状态"""
    # 预加载数据
    pipeline_data = get_pipeline_data()
    cost_data = get_cost_index_data()

    print("=" * 50)
    print("造价智能助手后端启动")
    print(f"  API Base URL: {API_BASE_URL or '(未配置)'}")
    print(f"  API Model:    {API_MODEL or '(未配置)'}")
    print(f"  API Key:      {'已配置' if API_KEY else '(未配置)'}")
    print(f"  工具数量:      {len(TOOLS)} 个")
    print(f"  管线指标数据:  {'已加载' if pipeline_data else '未加载'}")
    print(f"  造价指标数据:  {'已加载' if cost_data else '未加载'}")
    print("=" * 50)
    if not API_BASE_URL or not API_KEY or not API_MODEL:
        print("⚠️  警告：API 配置不完整，对话功能将不可用")
        print("   请在 .env 文件中配置 OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL")


@app.on_event("shutdown")
async def shutdown():
    """关闭 HTTP 客户端"""
    await client.aclose()


# ========== API 接口 ==========

@app.get("/api/config")
async def get_config():
    """获取前端可用的配置信息（不含密钥）"""
    configured = bool(API_BASE_URL and API_KEY and API_MODEL)
    return {
        "configured": configured,
        "model": API_MODEL,
        "systemPrompt": SYSTEM_PROMPT,
        "tools": [t["function"]["name"] for t in TOOLS]
    }


@app.post("/api/chat")
async def chat(request: Request):
    """
    聊天接口（支持流式和非流式，支持 Function Calling）
    请求体：{ messages: [...], stream: bool, temperature: float }
    """
    if not API_BASE_URL or not API_KEY or not API_MODEL:
        raise HTTPException(
            status_code=503,
            detail="API 未配置，请在服务端 .env 文件中设置 OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL"
        )

    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", True)
    temperature = body.get("temperature", 0.7)

    if not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    messages = prepare_messages(messages)

    # 构造 OpenAI 请求基础参数
    url = f"{API_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        if stream:
            # 流式响应：处理 Function Calling 循环
            return StreamingResponse(
                stream_chat_with_tools(messages, temperature, url, headers),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # 非流式响应
            result = await chat_with_tools(messages, temperature, url, headers)
            return result

    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到 API 服务：{str(e)}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="API 请求超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误：{str(e)}")


# ========== Function Calling 核心逻辑 ==========

def prepare_messages(messages):
    """合并用户 system prompt 与内置工具提示，避免丢失 Function Calling 规则"""
    prepared = [dict(message) for message in messages]
    full_system_prompt = SYSTEM_PROMPT + "\n" + TOOL_SYSTEM_PROMPT if SYSTEM_PROMPT else TOOL_SYSTEM_PROMPT
    full_system_prompt = full_system_prompt.strip()

    if prepared and prepared[0].get("role") == "system":
        existing_content = prepared[0].get("content", "").strip()
        prepared[0]["content"] = (existing_content + "\n\n" + full_system_prompt).strip()
    else:
        prepared.insert(0, {"role": "system", "content": full_system_prompt})

    return prepared

async def chat_with_tools(messages, temperature, url, headers, max_rounds=5):
    """非流式：支持多轮 Function Calling"""
    current_messages = list(messages)

    for round_idx in range(max_rounds):
        payload = {
            "model": API_MODEL,
            "messages": current_messages,
            "stream": False,
            "temperature": temperature,
            "tools": TOOLS,
            "tool_choice": "auto"
        }

        print(f"[Function Call] 第 {round_idx + 1} 轮请求，messages 数量: {len(current_messages)}")

        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", str(err_data))
            except Exception:
                err_msg = f"HTTP {resp.status_code}"
            raise HTTPException(status_code=resp.status_code, detail=err_msg)

        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]

        # 检查是否有工具调用
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # 没有工具调用，直接返回最终回复
            print(f"[Function Call] 无工具调用，直接返回回复")
            return data

        print(f"[Function Call] 检测到 {len(tool_calls)} 个工具调用")
        for tc in tool_calls:
            print(f"  → {tc['function']['name']}: {tc['function']['arguments']}")

        # 添加 assistant 消息（包含 tool_calls）
        current_messages.append(message)

        # 执行每个工具调用
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            tool_call_id = tool_call["id"]

            # 执行工具
            tool_result = execute_tool(tool_name, tool_args)
            print(f"[Function Call] 工具 {tool_name} 执行完成，结果长度: {len(tool_result)}")

            # 添加工具结果消息
            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result
            })

    # 达到最大轮次，返回最后一条消息
    print(f"[Function Call] 达到最大轮次 {max_rounds}")
    return data


async def stream_chat_with_tools(messages, temperature, url, headers, max_rounds=5):
    """流式：支持多轮 Function Calling"""
    current_messages = list(messages)

    for round_idx in range(max_rounds):
        payload = {
            "model": API_MODEL,
            "messages": current_messages,
            "stream": True,
            "temperature": temperature,
            "tools": TOOLS,
            "tool_choice": "auto"
        }

        # 收集流式响应，判断是否有 tool_call
        full_content = ""
        tool_calls_buffer = {}  # index -> {name, arguments, id}
        has_tool_call = False
        finish_reason = None

        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                err_text = await resp.aread()
                yield f"data: {{\"error\": \"HTTP {resp.status_code}: {err_text.decode('utf-8', errors='replace')}\"}}\n\n"
                return

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                delta = data.get("choices", [{}])[0].get("delta", {})
                finish_reason = data.get("choices", [{}])[0].get("finish_reason")

                # 检查是否有 tool_calls
                if "tool_calls" in delta and delta["tool_calls"]:
                    has_tool_call = True
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.get("id", ""),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": ""
                            }
                        if "function" in tc:
                            if tc["function"].get("name"):
                                tool_calls_buffer[idx]["name"] = tc["function"]["name"]
                            if tc["function"].get("arguments"):
                                tool_calls_buffer[idx]["arguments"] += tc["function"]["arguments"]

                # 普通文本内容
                if "content" in delta and delta["content"]:
                    full_content += delta["content"]
                    # 如果是第一轮且没有工具调用，透传给前端
                    if not has_tool_call:
                        yield f"{line}\n\n"

        # 如果没有工具调用，流式输出完成
        if not has_tool_call:
            yield "data: [DONE]\n\n"
            return

        # 有工具调用，先把完整的 assistant 消息加入历史
        assistant_msg = {"role": "assistant", "content": full_content or None}
        tool_calls_list = []
        for idx in sorted(tool_calls_buffer.keys()):
            tc = tool_calls_buffer[idx]
            tool_calls_list.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"]
                }
            })
        if tool_calls_list:
            assistant_msg["tool_calls"] = tool_calls_list
        current_messages.append(assistant_msg)

        # 向前端发送工具调用状态事件
        tool_status = {
            "event": "tool_call_start",
            "tools": [
                {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                for tc in tool_calls_list
            ]
        }
        yield f"data: {json.dumps(tool_status, ensure_ascii=False)}\n\n"

        # 执行每个工具并添加结果
        for tc in tool_calls_list:
            tool_name = tc["function"]["name"]
            tool_args = tc["function"]["arguments"]
            tool_call_id = tc["id"]

            # 执行工具
            tool_result = execute_tool(tool_name, tool_args)

            # 发送工具结果事件
            tool_result_event = {
                "event": "tool_call_result",
                "name": tool_name,
                "result": json.loads(tool_result) if tool_result.startswith("{") else tool_result
            }
            yield f"data: {json.dumps(tool_result_event, ensure_ascii=False)}\n\n"

            # 添加到消息历史
            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result
            })

        # 继续下一轮对话
        yield "data: {\"event\": \"thinking\"}\n\n"

    # 达到最大轮次，返回最终结果
    yield "data: [DONE]\n\n"


# ========== 静态文件服务（放在最后，避免覆盖 API 路由） ==========
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "chat.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
