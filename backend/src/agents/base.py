"""Agent 基类 — 统一 LLM 绑定、工具注册和执行接口。"""

import logging
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from src.config import get_settings

logger = logging.getLogger(__name__)


class BaseAgent:
    """所有 Agent 的基类，提供 LLM 绑定、工具注册和执行框架。"""

    name: str = "base_agent"
    description: str = ""
    system_prompt: str = ""

    def __init__(self):
        self._tools: list[BaseTool] = []
        self._llm = None
        self._llm_with_tools = None
        self._llm_available = False
        try:
            self._llm = self._create_llm()
            self._llm_available = True
        except Exception as e:
            logger.warning("LLM 初始化失败（工具直调用不受影响）: %s", e)

    def _create_llm(self) -> ChatOpenAI:
        settings = get_settings()
        return ChatOpenAI(
            base_url=settings.active_llm_base_url,
            api_key=settings.active_llm_api_key,
            model=settings.active_llm_model_name,
            temperature=settings.llm_temperature,
            timeout=120,
            max_retries=1,
        )

    def register_tool(self, tool: BaseTool):
        self._tools.append(tool)

    def register_tools(self, tools: list[BaseTool]):
        self._tools.extend(tools)

    def _get_llm_with_tools(self):
        if self._llm_with_tools is None and self._llm is not None:
            self._llm_with_tools = self._llm.bind_tools(self._tools)
        return self._llm_with_tools

    def run(self, query: str) -> dict:
        """执行用户查询。LLM 可用时走 Agent 链，不可用时直接返回工具结果。"""
        logs = []
        total_start = time.monotonic()

        if not self._llm_available or self._llm is None:
            logs.append({"step": "init", "status": "skip", "detail": "LLM 不可用"})
            return {
                "answer": "LLM 服务暂不可用，请使用面板按钮直接触发分析。",
                "tool_results": [],
                "debug_logs": logs,
            }

        settings = get_settings()
        logs.append({
            "step": "init",
            "status": "ok",
            "model": settings.active_llm_model_name,
            "provider": "ZhiPu" if settings.is_zhipu else "OLLAMA",
            "tools_registered": [t.name for t in self._tools],
        })

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=query),
        ]

        # --- 第一轮 LLM 调用：意图识别 + 工具选择 ---
        step_start = time.monotonic()
        try:
            llm = self._get_llm_with_tools()
            response = llm.invoke(messages)
            elapsed = round((time.monotonic() - step_start) * 1000)
        except Exception as e:
            elapsed = round((time.monotonic() - step_start) * 1000)
            logs.append({"step": "llm_call_1", "status": "error", "elapsed_ms": elapsed, "detail": str(e)})
            return {"answer": f"LLM 调用失败: {e}", "tool_results": [], "debug_logs": logs}

        # 记录 LLM 响应信息
        has_tool_calls = hasattr(response, "tool_calls") and response.tool_calls
        log_entry: dict = {
            "step": "llm_call_1",
            "status": "ok",
            "elapsed_ms": elapsed,
            "tool_calls_requested": [tc["name"] for tc in response.tool_calls] if has_tool_calls else [],
        }
        if not has_tool_calls and response.content:
            log_entry["direct_answer"] = True
            log_entry["response_preview"] = response.content[:200]
        logs.append(log_entry)

        tool_results = []
        if has_tool_calls:
            from langchain_core.messages import ToolMessage

            messages.append(response)

            # --- 逐个执行工具 ---
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                tool_obj = next((t for t in self._tools if t.name == tool_name), None)
                if tool_obj is None:
                    logs.append({"step": "tool_exec", "tool": tool_name, "status": "not_found"})
                    continue

                t_start = time.monotonic()
                try:
                    result = tool_obj.invoke(tool_args)
                    t_elapsed = round((time.monotonic() - t_start) * 1000)
                except Exception as e:
                    t_elapsed = round((time.monotonic() - t_start) * 1000)
                    logs.append({"step": "tool_exec", "tool": tool_name, "status": "error", "elapsed_ms": t_elapsed, "detail": str(e)})
                    continue

                result_str = str(result)
                truncated = len(result_str) > 10000
                result_text = result_str[:10000] + "\n...[数据已截断]" if truncated else result_str

                tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                })
                messages.append(
                    ToolMessage(content=result_text, tool_call_id=tool_call["id"])
                )

                logs.append({
                    "step": "tool_exec",
                    "tool": tool_name,
                    "status": "ok",
                    "elapsed_ms": t_elapsed,
                    "result_size": len(result_str),
                    "truncated": truncated,
                    "args": tool_args,
                })

            # --- 第二轮 LLM 调用：总结工具结果 ---
            step_start = time.monotonic()
            try:
                final_response = self._llm.invoke(messages)
                elapsed = round((time.monotonic() - step_start) * 1000)
                answer = final_response.content
                logs.append({"step": "llm_call_2", "status": "ok", "elapsed_ms": elapsed, "answer_length": len(answer)})
            except Exception as e:
                elapsed = round((time.monotonic() - step_start) * 1000)
                logs.append({"step": "llm_call_2", "status": "error", "elapsed_ms": elapsed, "detail": str(e)})
                tool_names = ", ".join(t["tool"] for t in tool_results)
                answer = f"工具 [{tool_names}] 已执行成功，但 LLM 生成总结超时。工具结果已返回，请查看下方数据。"
        else:
            answer = response.content

        total_elapsed = round((time.monotonic() - total_start) * 1000)
        logs.append({"step": "done", "total_ms": total_elapsed, "tools_used": len(tool_results)})

        return {"answer": answer, "tool_results": tool_results, "debug_logs": logs}

    def run_direct(self, tool_name: str) -> dict:
        """直接调用指定工具（用于一键触发场景，不经过 LLM）。"""
        tool_obj = next((t for t in self._tools if t.name == tool_name), None)
        if tool_obj is None:
            return {"error": f"工具 {tool_name} 不存在"}

        result = tool_obj.invoke({})
        return {"tool": tool_name, "result": result}
