# react_agent.py
# ReAct (Reasoning + Acting) Agent — independent of AgentController.
# Emits the SAME signals as AgentController so main_window can use one set of handlers.

import json
import logging
import re
import os
import importlib
import uuid

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from chat.model_manager import ModelManager
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
    action_match = re.search(r'Action\s*:\s*(\{.*\})', text, re.DOTALL)
    if action_match:
        try:
            return json.loads(action_match.group(1))
        except json.JSONDecodeError:
            pass
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
                 pre_filled_actions: list[dict] | None = None):
        self.model_name = model_name
        self.tool_schemas = tool_schemas
        self.function_map = function_map
        self.step_cb = step_cb
        self.obs_cb = obs_cb
        self.final_cb = final_cb
        self.error_cb = error_cb
        self.stop_flag = stop_flag
        self.thought_chain_collector = thought_chain_collector
        self.session_id = session_id
        self.history = history or []
        self.rag_docs = rag_docs or []
        self.tool_results: list[dict] = []
        self.pre_filled_actions = pre_filled_actions or []  # Stage 3 规划的工具调用
        self._pending_action: dict | None = None  # 预填充后 LLM 回复中解析出的待执行 Action

        self.model_manager = ModelManager()
        self._load_prompt()

    def _load_prompt(self):
        config = ConfigManager().get_assistant_config('react_agent')
        prompt_template = config.get('prompt_template', '')
        tool_schemas_str = json.dumps(self.tool_schemas, ensure_ascii=False, indent=2)
        self.system_prompt = prompt_template.replace('{tool_schemas}', tool_schemas_str)

    def run(self, user_input: str):
        """Execute the ReAct loop synchronously. Designed to be called from a QThread."""
        # 用历史消息初始化（克隆避免污染原始列表）
        messages = list(self.history)
        # ── 首轮：注入 RAG 上下文（仅本轮使用，不进入记忆）────────
        first_msg = user_input
        if self.rag_docs:
            first_msg = first_msg + f"\n__RAG_DOCS_JSON__:{json.dumps(self.rag_docs, ensure_ascii=False)}\n"
        messages.append(first_msg)

        # 每次运行使用唯一的 session_id，确保 system_prompt（含工具列表）
        # 被正确注入。复用同一 session 会导致 _prepare_messages 跳过新
        # system_prompt，模型看到的是旧工具列表。
        agent_llm_session = (
            f"react_agent_{self.session_id}_{uuid.uuid4().hex[:8]}"
            if self.session_id else None
        )

        # ── 预填充动作：先执行 Stage 3 预生成的工具调用 ──────────────────
        if self.pre_filled_actions:
            for action in self.pre_filled_actions:
                if self.stop_flag():
                    return

                tool_name = action.get("tool", "")
                tool_args = action.get("args", {})

                act_step_id = f"react_prefill_{tool_name}"
                self.step_cb(act_step_id, f"执行预填充工具: {tool_name}")

                if tool_name not in self.function_map:
                    obs_text = f"错误：预填充工具 '{tool_name}' 不存在"
                    self.obs_cb(act_step_id, False, obs_text)
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": 0,
                            "thought": f"预填充动作: {tool_name}",
                            "action": action,
                            "observation": obs_text,
                            "success": False,
                        })
                    # 预填充失败，回退到正常 ReAct 循环
                    break

                try:
                    result = self.function_map[tool_name](**tool_args)
                except Exception as e:
                    obs_text = f"预填充工具执行异常: {e}"
                    self.obs_cb(act_step_id, False, obs_text)
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": 0,
                            "thought": f"预填充动作: {tool_name}",
                            "action": action,
                            "observation": obs_text,
                            "success": False,
                        })
                    break

                success = result.get('success', False)
                obs_message = result.get('message', str(result))
                self.obs_cb(act_step_id, success, obs_message)

                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": 0,
                        "thought": f"预填充动作: {tool_name}",
                        "action": action,
                        "observation": obs_message,
                        "success": success,
                    })

                if not success:
                    self.error_cb(f"工具 '{tool_name}' 执行失败: {obs_message}")
                    return

                # 收集工具调用结果
                self.tool_results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result_summary": obs_message,
                })

                # 注入 Observation 供后续 ReAct 循环使用
                obs_json = json.dumps(result, ensure_ascii=False)
                messages.append(
                    f"Thought: 已预执行工具 {tool_name}，获取结果。\n"
                    f"Action: {json.dumps(action, ensure_ascii=False)}"
                )
                messages.append(f"Observation: {obs_json}")

            else:
                # 所有预填充动作都成功执行，让 LLM 基于结果继续推理
                if self.stop_flag():
                    return

                step_id = "react_think_final"
                self.step_cb(step_id, "生成最终回复...")
                try:
                    response = self.model_manager.chat(
                        model_name=self.model_name,
                        messages=messages,
                        system_prompt=self.system_prompt,
                        session_id=agent_llm_session,
                    )
                except Exception as e:
                    self.error_cb(f"模型调用失败: {e}")
                    return

                if self.stop_flag():
                    return

                logging.info(f"[ReAct] prefill-LLM response=\n{response}")

                # ── 检查 LLM 回复是否包含 Action（有则继续推理循环）────────
                next_action = _extract_action(response)
                if next_action:
                    # LLM 回复包含后续 Action → 标记当前步骤完成，进入 ReAct 循环
                    self.obs_cb(step_id, True, "检测到后续工具调用，继续执行")
                    messages.append(response)
                    messages.append("Observation: (等待执行)")
                    self._pending_action = next_action
                else:
                    # 无 Action：检查是否有 Final Answer
                    final_answer = _extract_final_answer(response)
                    result_text = final_answer if final_answer else response.strip()
                    self.obs_cb(step_id, True, result_text)
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": 1,
                            "thought": "根据预执行结果生成最终答案",
                            "action": None,
                            "observation": result_text,
                            "success": True,
                        })
                    self.final_cb(result_text)
                    return

        # ── 正常 ReAct 循环 ──────────────────────────────────────────────
        for iteration in range(1, MAX_ITERATIONS + 1):
            if self.stop_flag():
                return

            step_id = f"react_think_{iteration}"
            self.step_cb(step_id, f"第 {iteration} 轮 · 思考中...")

            # ── 如果有预填充阶段解析出的待执行 Action，直接执行它 ────────
            if self._pending_action is not None:
                action = self._pending_action
                self._pending_action = None  # 清除，只执行一次
                thought_part = "继续执行规划的后续工具调用"
                self.obs_cb(step_id, True, thought_part)
            else:
                # ── LLM call ─────────────────────────────────────────────
                try:
                    response = self.model_manager.chat(
                        model_name=self.model_name,
                        messages=messages,
                        system_prompt=self.system_prompt,
                        session_id=agent_llm_session,
                    )
                except Exception as e:
                    self.error_cb(f"模型调用失败: {e}")
                    return

                if self.stop_flag():
                    return

                logging.info(f"[ReAct] iter={iteration} response=\n{response}")

                # ── Check for Final Answer ────────────────────────────────
                final_answer = _extract_final_answer(response)
                if final_answer:
                    thought_text = re.split(r'Final Answer\s*:', response)[0].strip()
                    self.obs_cb(step_id, True, thought_text or "推理完成")
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": iteration,
                            "thought": thought_text or response.strip(),
                            "action": None,
                            "observation": thought_text or "推理完成",
                            "success": True,
                        })
                    self.final_cb(final_answer)
                    return

                # ── Check for Action ──────────────────────────────────────
                action = _extract_action(response)
                thought_part = re.split(r'Action\s*:', response)[0].strip()
                self.obs_cb(step_id, True, thought_part or response.strip())

                if action is None:
                    # 无 Action 且无 Final Answer → 把整个回复当作最终答案
                    if self.thought_chain_collector:
                        self.thought_chain_collector({
                            "iteration": iteration,
                            "thought": thought_part or response.strip(),
                            "action": None,
                            "observation": response.strip(),
                            "success": True,
                        })
                    self.final_cb(response.strip())
                    return

            # ── 执行工具 ────────────────────────────────────────────────
            tool_name = action.get('tool', '')
            tool_args = action.get('args', {})

            print(f"tool name: {tool_name}")
            print(f"tool args: {tool_args}")

            act_step_id = f"react_action_{iteration}"
            self.step_cb(act_step_id, f"调用工具: {tool_name}")

            if tool_name not in self.function_map:
                obs_text = f"错误：工具 '{tool_name}' 不存在"
                self.obs_cb(act_step_id, False, obs_text)
                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": iteration,
                        "thought": thought_part,
                        "action": action,
                        "observation": obs_text,
                        "success": False,
                    })
                self.error_cb(obs_text)
                return

            try:
                result = self.function_map[tool_name](**tool_args)
            except Exception as e:
                obs_text = f"工具执行异常: {e}"
                self.obs_cb(act_step_id, False, obs_text)
                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": iteration,
                        "thought": thought_part,
                        "action": action,
                        "observation": obs_text,
                        "success": False,
                    })
                self.error_cb(obs_text)
                return

            success = result.get('success', False)
            obs_message = result.get('message', str(result))
            self.obs_cb(act_step_id, success, obs_message)

            if not success:
                if self.thought_chain_collector:
                    self.thought_chain_collector({
                        "iteration": iteration,
                        "thought": thought_part,
                        "action": action,
                        "observation": obs_message,
                        "success": False,
                    })
                self.error_cb(f"工具 '{tool_name}' 执行失败: {obs_message}")
                return

            if self.thought_chain_collector:
                self.thought_chain_collector({
                    "iteration": iteration,
                    "thought": thought_part,
                    "action": action,
                    "observation": obs_message,
                    "success": True,
                })

            self.tool_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result_summary": obs_message,
            })

            # ── 追加到对话，供下一轮使用 ────────────────────────────────
            obs_json = json.dumps(result, ensure_ascii=False)
            messages.append(f"Thought: {thought_part}\nAction: {json.dumps(action, ensure_ascii=False)}")
            messages.append(f"Observation: {obs_json}")

        # Exceeded max iterations
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

    def __init__(self, agent: ReActAgent, user_input: str):
        super().__init__()
        self.agent = agent
        self.user_input = user_input
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        self._stop = False
        self.agent.stop_flag = lambda: self._stop

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

    def __init__(self, model: str, session_id: str | None = None,
                 tool_router=None):
        super().__init__()
        self.model_name = model
        self.session_id = session_id
        self._worker: _ReActWorker | None = None
        self._thought_chain: list = []
        self._tool_results: list[dict] = []       # 收集工具调用结果
        self._final_answer: str | None = None     # 捕获最终答案
        self._history: list[str] = []              # 格式化后的历史（注入 Agent）

        # 允许外部传入共享的 ToolRouter 实例，否则按需延迟创建
        self._tool_router = tool_router

        # Load all tools from experts.json (same approach as before – needed
        # for get_filtered_* lookups and for non-ReAct code paths)
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

        # ── Stage 1: 专家路由（带对话历史）────────────────────────────────
        filtered_schemas = self._tool_schemas
        filtered_func_map = self._function_map
        tool_plan: list[dict] = []  # 三阶段规划生成的工具调用计划

        try:
            # 延迟创建 ToolRouter（首次使用时才初始化）
            if self._tool_router is None:
                from sys_agent.tool_router import ToolRouter
                self._tool_router = ToolRouter(self.model_name)

            # UI 提示：正在路由
            self.workflow_step_started.emit(
                "react_routing", "正在分析任务并选择工具..."
            )

            # Stage 1: 专家路由（传入历史上下文）
            expert_names = self._tool_router.route_experts(
                user_input, history=self._history,
            )
            logging.info(f"[ReActController] Routed experts: {expert_names}")

            # Stage 2: 工具精选（传入历史上下文）
            tool_names = self._tool_router.select_tools(
                user_input, expert_names, history=self._history,
            )
            logging.info(f"[ReActController] Selected tools: {tool_names}")

            filtered_schemas = self._tool_router.get_filtered_schemas(tool_names) if tool_names else []
            filtered_func_map = self._tool_router.get_filtered_func_map(tool_names) if tool_names else {}

            # 路由完成，先发出完成信号让 UI 更新勾号
            self.workflow_step_finished.emit(
                "react_routing", True,
                f"已选择 {len(tool_names)} 个工具"
            )

            # Stage 3: 参数填充 — 获取被选工具的完整 schema，让 LLM 推断参数
            if tool_names:
                self.workflow_step_started.emit(
                    "react_param_fill", "正在推断工具参数..."
                )
                tool_plan = self._tool_router.fill_params(
                    user_input, tool_names, history=self._history,
                )
                self.workflow_step_finished.emit(
                    "react_param_fill", True,
                    f"已生成 {len(tool_plan)} 个工具调用计划"
                )

        except Exception as e:
            logging.error(
                f"[ReActController] Routing failed, using all tools: {e}",
                exc_info=True,
            )
            self.workflow_step_finished.emit(
                "react_routing", False,
                f"路由失败，将使用全部工具: {e}"
            )

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

        # ── 创建 ReActAgent（使用筛选后的工具）──────────────────────────
        agent = ReActAgent(
            model_name=self.model_name,
            tool_schemas=filtered_schemas,
            function_map=filtered_func_map,
            step_cb=lambda sid, txt: None,   # overwritten by worker
            obs_cb=lambda sid, ok, msg: None,
            final_cb=lambda ans: None,
            error_cb=lambda msg: None,
            stop_flag=lambda: False,
            thought_chain_collector=collect_thought,
            session_id=self.session_id,
            history=self._history,
            rag_docs=rag_docs,
            pre_filled_actions=tool_plan,
        )

        self._worker = _ReActWorker(agent, user_input)
        # Relay worker signals → controller signals
        self._worker.workflow_step_started.connect(self.workflow_step_started)
        self._worker.workflow_step_finished.connect(self.workflow_step_finished)
        self._worker.finished_signal.connect(capture_final)
        self._worker.finished_signal.connect(self.finished_signal)
        self._worker.error_signal.connect(self.error_signal)
        self._worker.start()

    def switch_model(self, model: str):
        self.model_name = model
        # 模型切换后丢弃缓存的 router，下次 start_workflow 时按新模型重建
        self._tool_router = None
