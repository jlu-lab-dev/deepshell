# react_agent.py
# ReAct (Reasoning + Acting) Agent — independent of AgentController.
# Emits the SAME signals as AgentController so main_window can use one set of handlers.

import json
import logging
import re
import os
import importlib

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from chat.model_manager import ModelManager
from config.config_manager import ConfigManager


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
                 step_cb, obs_cb, final_cb, error_cb, stop_flag):
        self.model_name = model_name
        self.tool_schemas = tool_schemas
        self.function_map = function_map
        self.step_cb = step_cb
        self.obs_cb = obs_cb
        self.final_cb = final_cb
        self.error_cb = error_cb
        self.stop_flag = stop_flag

        self.model_manager = ModelManager()
        self._load_prompt()

    def _load_prompt(self):
        config = ConfigManager().get_assistant_config('react_agent')
        prompt_template = config.get('prompt_template', '')
        tool_schemas_str = json.dumps(self.tool_schemas, ensure_ascii=False, indent=2)
        self.system_prompt = prompt_template.replace('{tool_schemas}', tool_schemas_str)

    def run(self, user_input: str):
        """Execute the ReAct loop synchronously. Designed to be called from a QThread."""
        # Conversation history: alternating user/assistant messages
        messages = [user_input]
        session_id = None  # stateless per request

        for iteration in range(1, MAX_ITERATIONS + 1):
            if self.stop_flag():
                return

            step_id = f"react_think_{iteration}"
            self.step_cb(step_id, f"第 {iteration} 轮 · 思考中...")

            # ── LLM call ─────────────────────────────────────────────────
            try:
                response = self.model_manager.chat(
                    model_name=self.model_name,
                    messages=messages,
                    system_prompt=self.system_prompt,
                    session_id=session_id,
                )
            except Exception as e:
                self.error_cb(f"模型调用失败: {e}")
                return

            if self.stop_flag():
                return

            logging.info(f"[ReAct] iter={iteration} response=\n{response}")

            # ── Check for Final Answer ────────────────────────────────────
            final_answer = _extract_final_answer(response)
            if final_answer:
                # Extract thought text (everything before Final Answer:)
                thought_text = re.split(r'Final Answer\s*:', response)[0].strip()
                self.obs_cb(step_id, True, thought_text or "推理完成")
                self.final_cb(final_answer)
                return

            # ── Check for Action ──────────────────────────────────────────
            action = _extract_action(response)
            thought_part = re.split(r'Action\s*:', response)[0].strip()
            self.obs_cb(step_id, True, thought_part or response.strip())

            if action is None:
                # No action and no final answer — treat whole response as final answer
                self.final_cb(response.strip())
                return

            tool_name = action.get('tool', '')
            tool_args = action.get('args', {})

            print(f"tool name: {tool_name}")
            print(f"tool args: {tool_args}")

            # ── Execute tool ──────────────────────────────────────────────
            act_step_id = f"react_action_{iteration}"
            self.step_cb(act_step_id, f"调用工具: {tool_name}")

            if tool_name not in self.function_map:
                obs_text = f"错误：工具 '{tool_name}' 不存在"
                self.obs_cb(act_step_id, False, obs_text)
                self.error_cb(obs_text)
                return

            try:
                result = self.function_map[tool_name](**tool_args)
            except Exception as e:
                obs_text = f"工具执行异常: {e}"
                self.obs_cb(act_step_id, False, obs_text)
                self.error_cb(obs_text)
                return

            success = result.get('success', False)
            obs_message = result.get('message', str(result))
            self.obs_cb(act_step_id, success, obs_message)

            if not success:
                self.error_cb(f"工具 '{tool_name}' 执行失败: {obs_message}")
                return

            # ── Append to conversation for next iteration ─────────────────
            # Simulate multi-turn: append assistant response + observation as next user message
            obs_json = json.dumps(result, ensure_ascii=False)
            messages.append(response)           # assistant turn
            messages.append(f"Observation: {obs_json}")  # observation as next user turn

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

    def __init__(self, model: str):
        super().__init__()
        self.model_name = model
        self._worker: _ReActWorker | None = None

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

        return schemas, func_map

    # ── Public API (mirror AgentController) ──────────────────────────────

    @pyqtSlot(str)
    def start_workflow(self, user_input: str):
        """Entry point called via QMetaObject.invokeMethod from main thread."""
        # Stop previous worker if still running
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        agent = ReActAgent(
            model_name=self.model_name,
            tool_schemas=self._tool_schemas,
            function_map=self._function_map,
            step_cb=lambda sid, txt: None,   # overwritten by worker
            obs_cb=lambda sid, ok, msg: None,
            final_cb=lambda ans: None,
            error_cb=lambda msg: None,
            stop_flag=lambda: False,
        )

        self._worker = _ReActWorker(agent, user_input)
        # Relay worker signals → controller signals
        self._worker.workflow_step_started.connect(self.workflow_step_started)
        self._worker.workflow_step_finished.connect(self.workflow_step_finished)
        self._worker.finished_signal.connect(self.finished_signal)
        self._worker.error_signal.connect(self.error_signal)
        self._worker.start()

    def switch_model(self, model: str):
        self.model_name = model
