# react_agent.py
# ReAct (Reasoning + Acting) Agent — independent of AgentController.
# Emits the SAME signals as AgentController so main_window can use one set of handlers.

import json
import logging
import re
import os
import importlib
import hashlib
import threading
import time
import uuid
from functools import partial

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from chat.model_manager import ModelManager
from sys_agent.tool_registry import ToolRegistry
from sys_agent.tool_executor import ToolExecutor
from sys_agent.agent_trace import TraceRecorder
from config.config_manager import ConfigManager
from chat.message_helpers import parse_message_content, get_agent_memory_content, get_summary_text, is_compressed


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _extract_json_obj(text: str) -> dict | None:
    """Extract the first {...} or [...] JSON object from text."""
    match = re.search(r'(\{.*?\}|\[.*?\])', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_action(text: str) -> dict | None:
    """
    Parse an Action line like:
        Action: {"tool": "foo", "args": {...}}
    Returns dict or None.
    """
    # JSONDecoder.raw_decode 能正确处理嵌套对象，也不会把后续 Thought/Observation 一起吞掉。
    action_match = re.search(r"Action\s*:\s*", text)
    if not action_match:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[action_match.end():].lstrip())
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_final_answer(text: str) -> str | None:
    """Return the content after 'Final Answer:' if present."""
    match = re.search(r'Final Answer\s*:\s*(.*)', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


# ──────────────────────────────────────────────
# Core ReAct logic (pure Python, no Qt)
# ──────────────────────────────────────────────

MAX_ITERATIONS = 8
APPROVAL_WAIT_SECONDS = 60.0


class ReActAgent:
    """
    Pure-Python ReAct loop.
    Caller supplies:
      - model_name       : str
      - tool_schemas     : list[dict]  (OpenAI-style function schema)
      - function_map     : dict[str, callable]
      - step_cb          : callable(step_id, display_text)
      - obs_cb           : callable(step_id, success, message)
      - final_cb         : callable(final_answer)
      - error_cb         : callable(error_message)
      - stop_flag        : callable() -> bool   (returns True to abort)
    """

    def __init__(self, model_name: str, tool_schemas: list, function_map: dict,
                 step_cb, obs_cb, final_cb, error_cb, stop_flag,
                 thought_chain_collector=None,
                 session_id: str | None = None,
                 history: list | None = None,
                 rag_docs: list | None = None,
                 trace_recorder: TraceRecorder | None = None,
                 model_manager=None,
                 approval_cb=None,
                 allow_approved_write: bool = True):
        self.model_name = model_name
        self.model_manager = model_manager if model_manager is not None else ModelManager()
        report_handler = function_map.get('generate_report_text')
        if getattr(report_handler, '__module__', '') == 'sys_agent.toolkits.data_analysis_tools':
            function_map = dict(function_map)
            function_map['generate_report_text'] = partial(report_handler, _llm=lambda prompt:
                self.model_manager.chat(model_name=self.model_name, messages=[prompt],
                    system_prompt='根据用户提供的数据生成报告，不调用工具。',
                    session_id='agent_report_' + uuid.uuid4().hex))
        # 按 GUI/历史评测配置注册工具；所有 Action 统一经过 Executor。
        self.tool_registry = ToolRegistry.from_existing(tool_schemas, function_map,
                                                       allow_approved_write=allow_approved_write)
        self.tool_schemas = self.tool_registry.get_tool_schemas()
        self.executor = ToolExecutor(self.tool_registry)
        self.step_cb = step_cb
        self.obs_cb = obs_cb
        self.final_cb = final_cb
        self.error_cb = error_cb
        self.stop_flag = stop_flag
        self.approval_cb = approval_cb
        self.thought_chain_collector = thought_chain_collector
        self.session_id = session_id
        self.history = history or []
        self.rag_docs = rag_docs or []
        self.tool_results: list[dict] = []  # 收集本次运行的工具调用结果
        self.trace = trace_recorder
        if self.trace is None and os.environ.get("DEEPSHELL_AGENT_TRACE") == "1":
            self.trace = TraceRecorder(os.environ.get("DEEPSHELL_AGENT_TRACE_DIR", "logs/agent_traces"))

        self._load_prompt()

    def _load_prompt(self):
        config = ConfigManager().get_assistant_config('react_agent')
        prompt_template = config.get('prompt_template', '')
        tool_schemas_str = json.dumps(self.tool_schemas, ensure_ascii=False, indent=2)
        self.system_prompt = prompt_template.replace('{tool_schemas}', tool_schemas_str)
        if self.tool_registry.full_tools:
            permission = ("可使用本轮列出的全部工具。只读查询可直接调用；有副作用或额外模型外传的操作"
                          "需等待本轮 GUI 用户逐次批准。拒绝、关闭或超时后不能执行，也不能绕用 Shell 规避审批。"
                          "成功与否以 Observation 为准；不得在审批前声称已经完成。create_text_file 仍限专用工作区且不能覆盖。")
        elif self.tool_registry.get("create_text_file") is not None:
            permission = ("仅 create_text_file 可申请在专用工作区创建新的 .txt 文件，必须等待本轮用户批准；"
                          "不得承诺审批前已完成写入。不得写入其他目录、覆盖、删除文件、运行程序、关机或执行 Shell。")
        else:
            permission = "不具备文件写入、删除、运行程序、关机或执行 Shell 命令的权限；相关请求应说明当前能力限制。"
        self.system_prompt = self.system_prompt.replace('{tool_permissions}', permission)

    def _trace(self, kind: str, **kwargs):
        """脱敏 Trace 写入失败不能中断 Agent；日志只记录异常类别。"""
        if self.trace is not None:
            try:
                self.trace.record(kind, **kwargs)
            except Exception as exc:
                logging.warning("[ReAct] trace recording failed: %s", type(exc).__name__)

    def _finish_trace(self, reason: str, iteration: int | None = None):
        if self.trace is not None:
            try:
                self.trace.finish(reason, iteration=iteration)
            except Exception as exc:
                logging.warning("[ReAct] trace finish failed: %s", type(exc).__name__)

    def run(self, user_input: str):
        """Execute the ReAct loop synchronously. Designed to be called from a QThread."""
        # 用历史消息初始化（克隆避免污染原始列表）
        messages = list(self.history)
        # ── 首轮：注入 RAG 上下文（仅本轮使用，不进入记忆）────────
        first_msg = user_input
        if self.rag_docs:
            first_msg = first_msg + f"\n__RAG_DOCS_JSON__:{json.dumps(self.rag_docs, ensure_ascii=False)}\n"
        messages.append(first_msg)

        # Agent 内部 LLM 调用使用派生的 session_id，避免与普通 Chat 记忆混淆
        agent_llm_session = f"react_agent_{self.session_id}" if self.session_id else None
        consecutive_errors = 0  # 限制连续模型格式/参数错误，避免无意义循环。
        self._trace("task_started", model_name=self.model_name)

        for iteration in range(1, MAX_ITERATIONS + 1):
            if self.stop_flag():
                self._finish_trace("cancelled", iteration)
                return

            step_id = f"react_think_{iteration}"
            self.step_cb(step_id, f"第 {iteration} 轮 · 思考中...")

            # ── LLM call ─────────────────────────────────────────────────
            try:
                response = self.model_manager.chat(
                    model_name=self.model_name,
                    messages=messages,
                    system_prompt=self.system_prompt,
                    session_id=agent_llm_session,
                )
            except Exception as e:
                self._finish_trace("model_error", iteration)
                self.error_cb(f"模型调用失败: {e}")
                return

            if self.stop_flag():
                self._finish_trace("cancelled", iteration)
                return

            self._trace("model_result", iteration=iteration, code="RESPONSE_RECEIVED")
            # 避免把完整模型消息/工具参数写入日志（可能包含用户敏感输入）。
            logging.debug("[ReAct] iteration=%s received_model_response", iteration)

            # ── Check for Final Answer ────────────────────────────────────
            final_answer = _extract_final_answer(response)
            if final_answer:
                # Extract thought text (everything before Final Answer:)
                thought_text = re.split(r'Final Answer\s*:', response)[0].strip()
                self.obs_cb(step_id, True, thought_text or "推理完成")
                # ── 收集推理链：Final Answer 分支 ──
                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": iteration,
                        "thought": thought_text or response.strip(),
                        "action": None,
                        "observation": thought_text or "推理完成",
                        "success": True,
                    })
                self._finish_trace("completed", iteration)
                self.final_cb(final_answer)
                return

            # ── Check for Action ──────────────────────────────────────────
            action = _extract_action(response)
            thought_part = re.split(r'Action\s*:', response)[0].strip()
            self.obs_cb(step_id, True, thought_part or response.strip())

            if action is None:
                # 模型明确尝试 Action 却没给出合法 JSON，不能把错误格式当成最终答案。
                if re.search(r"Action\s*:", response):
                    consecutive_errors += 1
                    obs_text = "PARSE_ERROR: Action 后必须是合法 JSON，例如 Action: {\"tool\":\"get_current_directory\",\"args\":{}}"
                    self.obs_cb(step_id, False, obs_text)
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": iteration, "thought": thought_part,
                            "action": None, "observation": obs_text, "success": False,
                        })
                    if consecutive_errors >= 2:
                        self._finish_trace("parse_error", iteration)
                        self.error_cb("模型连续两次生成了无效工具调用，已停止以避免误执行。")
                        return
                    messages.extend([response, f"Observation: {obs_text}"])
                    continue

                # 没有 Action / Final Answer 的正常闲聊仍保留旧版兼容行为。
                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": iteration, "thought": thought_part or response.strip(),
                        "action": None, "observation": response.strip(), "success": True,
                    })
                self._finish_trace("plain_answer", iteration)
                self.final_cb(response.strip())
                return

            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})
            act_step_id = f"react_action_{iteration}"
            self.step_cb(act_step_id, f"调用工具: {tool_name}")

            # 唯一执行入口：allowlist -> Pydantic 校验 -> 实际处理函数。
            tool_result = self.executor.execute(tool_name, tool_args)
            history_action = action
            if tool_name == "create_text_file":
                args = tool_args if isinstance(tool_args, dict) else {}
                content = args.get("content", "")
                history_action = {"tool": tool_name, "args": {
                    "filename": args.get("filename", ""),
                    "content_sha256": hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
                    if isinstance(content, str) else "INVALID_CONTENT",
                }}
            elif tool_result.code == "PENDING_APPROVAL":
                history_action = {"tool": tool_name, "args": {
                    "argument_keys": sorted(tool_args),
                    "arguments_sha256": hashlib.sha256(json.dumps(tool_args, ensure_ascii=False,
                        sort_keys=True).encode('utf-8')).hexdigest(),
                }}
            if tool_result.code == "PENDING_APPROVAL":
                self._trace("tool_result", iteration=iteration, tool=tool_name,
                            code="PENDING_APPROVAL", success=False, argument_keys=list(tool_args))
                request_id = tool_result.data["request_id"]
                review = self.executor.get_pending_approval(request_id)
                decision = False
                if review is not None and self.approval_cb is not None and not self.stop_flag():
                    try:
                        decision = self.approval_cb(review)
                    except Exception:
                        decision = False
                if self.stop_flag():
                    self.executor.resolve_pending_approval(request_id, False)
                    self._finish_trace("cancelled", iteration)
                    return
                tool_result = self.executor.resolve_pending_approval(request_id, decision is True)
                if decision is None and tool_result.code == "APPROVAL_DENIED":
                    tool_result = tool_result.model_copy(update={
                        "code": "APPROVAL_TIMEOUT", "message": "审批等待超时，操作未执行"})
            result = tool_result.model_dump(mode="json")
            self._trace("tool_result", iteration=iteration, tool=tool_name,
                        code=tool_result.code, success=tool_result.success,
                        elapsed_ms=tool_result.elapsed_ms,
                        argument_keys=list(tool_args) if isinstance(tool_args, dict) else [])
            success = tool_result.success
            obs_message = f"[{tool_result.code}] {tool_result.message}"
            self.obs_cb(act_step_id, success, obs_message)
            if self.thought_chain_collector:
                self.thought_chain_collector({
                    "iteration": iteration,
                    "thought": thought_part or response.strip(),
                    "action": history_action, "observation": obs_message, "success": success,
                    "tool_result": result,
                })

            if success:
                consecutive_errors = 0
                self.tool_results.append({
                    "tool": tool_name, "args": history_action.get("args", {}), "result_summary": obs_message,
                })
            elif tool_result.code in {
                "APPROVAL_DENIED", "APPROVAL_EXPIRED", "APPROVAL_INVALID", "APPROVAL_TIMEOUT", "WRITE_FAILED"
            }:
                self._finish_trace("tool_error" if tool_result.code == "WRITE_FAILED" else "permission_denied", iteration)
                self.final_cb(f"操作未执行：{tool_result.message}。")
                return
            elif tool_result.code == "PERMISSION_DENIED":
                # 未授权工具绝不执行，也不让模型反复请求同一个危险操作。
                self._finish_trace("permission_denied", iteration)
                self.error_cb(f"工具 '{tool_name}' 未获得执行权限。")
                return
            elif not tool_result.retryable:
                self._finish_trace("tool_error", iteration)
                self.error_cb(f"工具 '{tool_name}' 执行失败: {obs_message}")
                return
            else:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    self._finish_trace("tool_error", iteration)
                    self.error_cb(f"连续两次工具调用失败，最后错误：{obs_message}")
                    return

            # 保持原来的 ReAct 文本协议，给模型一次修正参数/工具选择的机会。
            messages.append(response)
            messages.append(f"Observation: {json.dumps(result, ensure_ascii=False)}")

        # Exceeded max iterations
        self._finish_trace("max_iterations", MAX_ITERATIONS)
        self.error_cb(f"已达到最大推理轮次 ({MAX_ITERATIONS})，任务未完成。")


# ──────────────────────────────────────────────
# Qt Wrapper
# ──────────────────────────────────────────────

class _ReActWorker(QThread):
    """Internal worker thread that runs the ReAct loop."""

    # Mirror AgentController signals exactly
    workflow_step_started = pyqtSignal(str, str)
    workflow_step_finished = pyqtSignal(str, bool, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    approval_requested = pyqtSignal(str, str, str, str, str)
    operation_approval_requested = pyqtSignal(object)
    approval_closed = pyqtSignal(str)

    def __init__(self, agent: ReActAgent, user_input: str):
        super().__init__()
        self.agent = agent
        self.user_input = user_input
        self._stop = False
        self._approval_event = threading.Event()
        self._approval_lock = threading.Lock()
        self._approval_id = None
        self._approval_decision = False

    def stop(self):
        self._stop = True
        self._approval_event.set()

    def resolve_approval(self, request_id: str, approved: bool):
        """只更新锁和事件；可由 GUI 主线程直接通知 Worker。"""
        with self._approval_lock:
            if request_id != self._approval_id or self._approval_event.is_set():
                return
            self._approval_decision = approved is True
            self._approval_event.set()

    def ask_approval(self, review: dict) -> bool | None:
        request_id = review["request_id"]
        with self._approval_lock:
            self._approval_id = request_id
            self._approval_decision = False
            self._approval_event.clear()
        deadline = time.monotonic() + APPROVAL_WAIT_SECONDS
        if 'tool' in review:
            self.operation_approval_requested.emit(review)
        else:
            self.approval_requested.emit(request_id, review["filename"], review["workspace"],
                                         review["content"], review["sha256"])
        try:
            while not self._stop and time.monotonic() < deadline:
                if self._approval_event.wait(timeout=min(0.2, max(0.0, deadline - time.monotonic()))):
                    break
            with self._approval_lock:
                if self._stop:
                    return False
                if time.monotonic() >= deadline or not self._approval_event.is_set():
                    return None
                return self._approval_decision
        finally:
            with self._approval_lock:
                self._approval_id = None
            self.approval_closed.emit(request_id)

    def run(self):
        self.agent.stop_flag = lambda: self._stop
        self.agent.approval_cb = self.ask_approval

        self.agent.step_cb = lambda sid, txt: self.workflow_step_started.emit(sid, txt)
        self.agent.obs_cb = lambda sid, ok, msg: self.workflow_step_finished.emit(sid, ok, msg)
        self.agent.final_cb = lambda ans: self.finished_signal.emit(ans)
        self.agent.error_cb = lambda msg: self.error_signal.emit(msg)

        self.agent.run(self.user_input)


class ReActAgentController(QObject):
    """
    Drop-in companion to AgentController.
    Exposes exactly the same signals so main_window handlers work without changes.
    """

    # Mirror AgentController signals
    normal_update_signal = pyqtSignal(str)
    normal_finished_signal = pyqtSignal(str)
    workflow_step_started = pyqtSignal(str, str)
    workflow_step_finished = pyqtSignal(str, bool, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    approval_requested = pyqtSignal(str, str, str, str, str)
    operation_approval_requested = pyqtSignal(object)
    approval_closed = pyqtSignal(str)

    def __init__(self, model: str, session_id: str | None = None):
        super().__init__()
        self.model_name = model
        self.session_id = session_id
        self._worker: _ReActWorker | None = None
        self._thought_chain: list = []
        self._tool_results: list[dict] = []       # 收集工具调用结果
        self._final_answer: str | None = None     # 捕获最终答案
        self._history: list[str] = []              # 格式化后的历史（注入 Agent）

        # Load all tools from experts.json (same approach as AgentController)
        self._tool_schemas, self._function_map = self._load_all_tools()

    # ── Tool loading ──────────────────────────────────────────────────────

    def _load_all_tools(self) -> tuple[list, dict]:
        """Load every tool schema + implementation from sys_agent/toolkits."""
        schemas = []
        func_map = {}
        try:
            base_path = os.path.dirname(__file__)
            experts_path = os.path.join(base_path, "experts.json")
            with open(experts_path, "r", encoding="utf-8") as f:
                experts = json.load(f)

            for expert in experts:
                if expert.get("tools_definition_file"):
                    def_path = os.path.join(base_path, expert["tools_definition_file"])
                    with open(def_path, "r", encoding="utf-8") as f:
                        schemas.extend(json.load(f))

                if expert.get("tools_implementation_module"):
                    module = importlib.import_module(expert["tools_implementation_module"])
                    if hasattr(module, "FUNCTION_MAP"):
                        func_map.update(module.FUNCTION_MAP)

        except Exception as e:
            logging.error(f"[ReActAgentController] Failed to load tools: {e}")

        # Controller 保留原有工具清单，ReActAgent 初始化时按白名单过滤提示词与执行入口。
        return schemas, func_map

    # ── Public API (mirror AgentController) ──────────────────────────────

    def load_history(self, conversation_repo, session_id: str):
        """
        从数据库加载历史对话并格式化为字符串列表，供注入到 Agent 的 messages 中。
        支持 summary 类型消息；跳过 compressed 标记消息；超出字符限制时截断。
        """
        self.session_id = session_id
        self._history = []
        if not conversation_repo or not session_id:
            return

        db_messages = conversation_repo.get_messages(session_id)
        for msg in db_messages:
            if msg.role not in ("user", "assistant", "system"):
                continue

            # 已压缩的原始消息：UI 可渲染，但不注入 Agent 历史
            if is_compressed(msg.content):
                continue

            data = parse_message_content(msg.content)
            msg_type = data.get("type", "text")

            if msg_type == "summary":
                summary = get_summary_text(msg.content)
                if summary:
                    self._history.append(f"[历史对话摘要]\n{summary}")
                continue

            if msg_type == "text":
                text = data.get("content", "")
                if msg.role == "user":
                    self._history.append(f"用户问：{text}")
                else:
                    self._history.append(f"助手回答：{text}")
            elif msg_type == "agent_memory":
                # 紧凑记忆格式：优先使用
                entries = get_agent_memory_content(msg.content)
                self._history.extend(entries)
            elif msg_type == "agent_workflow":
                # 兼容旧数据：从完整工作流中提取工具结果和最终答案
                thought_chain = data.get("thought_chain", [])
                for tc in thought_chain:
                    if tc.get("action") and tc.get("success"):
                        tool_name = tc["action"].get("tool", "unknown")
                        obs = tc.get("observation", "")
                        self._history.append(
                            f"Observation (tool={tool_name}): {obs}"
                        )
                final = data.get("final_result", "")
                if final:
                    self._history.append(f"助手回答：{final}")

        # 委托 MemoryCompressor 做字符数截断（从头部丢弃，超限部分丢弃）
        from chat.memory_compressor import MemoryCompressor
        self._history = MemoryCompressor().compress_agent_history(self._history)

        logging.info(
            f"[ReActController] Loaded {len(self._history)} history entries "
            f"for session={session_id[:8] if session_id else 'None'}.."
        )

    @pyqtSlot(str, list)
    def start_workflow(self, user_input: str, rag_docs: list = None):
        """Entry point called via QMetaObject.invokeMethod from main thread."""
        # Stop previous worker if still running
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        self._thought_chain = []
        self._tool_results = []
        self._final_answer = None

        def collect_thought(entry: dict):
            self._thought_chain.append(entry)
            # 同时收集工具调用结果（用于记忆持久化）
            if entry.get("action") and entry.get("success"):
                action = entry["action"]
                self._tool_results.append({
                    "tool": action.get("tool", "unknown"),
                    "args": action.get("args", {}),
                    "result_summary": entry.get("observation", ""),
                })

        def capture_final(answer: str):
            self._final_answer = answer
            # 将本次运行结果追加到 _history（供下次调用使用）
            for tr in self._tool_results:
                self._history.append(
                    f"Observation (tool={tr['tool']}): {tr['result_summary']}"
                )
            if answer:
                self._history.append(f"助手回答：{answer}")

        agent = ReActAgent(
            model_name=self.model_name,
            tool_schemas=self._tool_schemas,
            function_map=self._function_map,
            step_cb=lambda sid, txt: None,   # overwritten by worker
            obs_cb=lambda sid, ok, msg: None,
            final_cb=lambda ans: None,
            error_cb=lambda msg: None,
            stop_flag=lambda: False,
            thought_chain_collector=collect_thought,
            session_id=self.session_id,
            history=self._history,
            rag_docs=rag_docs,
        )

        self._worker = _ReActWorker(agent, user_input)
        # Relay worker signals → controller signals
        self._worker.workflow_step_started.connect(self.workflow_step_started)
        self._worker.workflow_step_finished.connect(self.workflow_step_finished)
        self._worker.finished_signal.connect(capture_final)
        self._worker.finished_signal.connect(self.finished_signal)
        self._worker.error_signal.connect(self.error_signal)
        self._worker.approval_requested.connect(self.approval_requested)
        self._worker.operation_approval_requested.connect(self.operation_approval_requested)
        self._worker.approval_closed.connect(self.approval_closed)
        self._worker.start()

    def resolve_approval(self, request_id: str, approved: bool):
        if self._worker is not None:
            self._worker.resolve_approval(request_id, approved)

    def cancel_pending_approval(self):
        if self._worker is not None:
            self._worker.stop()

    def switch_model(self, model: str):
        self.model_name = model
