# agent_controller.py

import json
import logging
import re
import os
import importlib
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

from chat.chat_task import ChatTask
from sys_agent.agent_task import ProjectManagerTask, ExpertToolRecommenderTask, ChiefPlannerTask


def extract_json_from_string(text: str) -> str | None:
    match = re.search(r'({.*}|\[.*\])', text, re.DOTALL)
    if match: return match.group(0)
    return None


class AgentController(QObject):
    # For simple fallback chats
    normal_update_signal = pyqtSignal(str)
    normal_finished_signal = pyqtSignal(str)

    # New signals for structured workflow UI
    # pyqtSignal(step_id, display_text)
    workflow_step_started = pyqtSignal(str, str)
    # pyqtSignal(step_id, success_bool, result_text)
    workflow_step_finished = pyqtSignal(str, bool, str)

    # Final signal when the entire workflow is done
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # --- 初始化所有智能体Task ---
        self.pm_task = ProjectManagerTask()
        self.expert_task = ExpertToolRecommenderTask()
        self.planner_task = ChiefPlannerTask()
        self.fallback_chat_task = ChatTask()

        # --- 连接信号 ---
        self.pm_task.complete_signal.connect(self.handle_dispatch_result)
        self.expert_task.complete_signal.connect(self.handle_expert_recommendation)
        self.planner_task.complete_signal.connect(self.execute_workflow)
        self.fallback_chat_task.update_signal.connect(self.normal_update_signal)
        self.fallback_chat_task.complete_signal.connect(self.normal_finished_signal)

        # --- 动态加载专家和工具定义 ---
        self._load_definitions_and_functions()

        self.execution_context = {}

    def _load_definitions_and_functions(self):
        """动态加载所有专家的定义，并合并所有工具的实现函数"""
        self.experts = []
        self.expert_briefs = []
        self.expert_tool_definitions = {}
        self.MASTER_FUNCTION_MAP = {}  # 创建一个总的FUNCTION_MAP

        try:
            base_path = os.path.dirname(__file__)
            with open(os.path.join(base_path, "experts.json"), "r", encoding="utf-8") as f:
                self.experts = json.load(f)

            self.expert_briefs = [{"name": e["name"], "description": e["description"]} for e in self.experts]

            for expert in self.experts:
                expert_name = expert["name"]

                # 加载工具定义JSON
                if expert["tools_definition_file"]:
                    with open(os.path.join(base_path, expert["tools_definition_file"]), "r", encoding="utf-8") as f:
                        self.expert_tool_definitions[expert_name] = json.load(f)

                # 动态导入工具实现模块并合并FUNCTION_MAP
                if expert["tools_implementation_module"]:
                    module = importlib.import_module(expert["tools_implementation_module"])
                    if hasattr(module, 'FUNCTION_MAP'):
                        self.MASTER_FUNCTION_MAP.update(module.FUNCTION_MAP)

        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load agent definitions or tool functions: {e}")

    @pyqtSlot(str)
    def start_workflow(self, user_input: str):
        """入口：启动项目经理进行专家调度"""
        self.execution_context = {"user_input": user_input}
        # NOTE: We DON'T emit a signal here immediately. We wait for the dispatcher's result
        # to decide if it's a real workflow or just a simple chat.

        topic = (f"【专家团队列表】\n{json.dumps(self.expert_briefs, ensure_ascii=False, indent=2)}\n\n"
                 f"【用户项目需求】\n{user_input}")
        self.pm_task.set_topic(topic)
        self.pm_task.start()

    @pyqtSlot(str)
    def handle_dispatch_result(self, dispatch_raw: str):
        """
        处理项目经理返回的专家列表。
        - 如果列表中只包含 fallback 专家，则进入聊天模式 (no workflow UI)。
        - 否则，启动工作流UI并继续。
        """
        logging.info(f"--- Raw Dispatcher Response ---:\n{dispatch_raw}\n---------------------------------")

        dispatch_json = extract_json_from_string(dispatch_raw)
        if not dispatch_json:
            self.error_signal.emit("Error: The dispatcher returned an invalid format.")
            return

        try:
            selected_expert_names = json.loads(dispatch_json.strip())
            if not isinstance(selected_expert_names, list):
                raise TypeError("Dispatcher response is not a list.")
        except (json.JSONDecodeError, TypeError) as e:
            self.error_signal.emit(f"Error: Could not parse dispatcher response. Details: {e}")
            return

        # Case 1: It's a simple chat, NOT a workflow.
        if not selected_expert_names or (
                len(selected_expert_names) == 1 and selected_expert_names[0] == "general_fallback_expert"):
            user_input = self.execution_context.get("user_input")
            self.fallback_chat_task.set_topic(user_input)
            self.fallback_chat_task.start()
            return

        # Case 2: It IS a workflow. Now we start showing the UI steps.
        self.workflow_step_started.emit("dispatch", "DeepShell 正在生成工作流，请稍等...")
        self.workflow_step_finished.emit("dispatch", True, f"工作流生成完成")

        self.execution_context.update({
            "experts_to_consult": selected_expert_names,
            "recommended_tools": set(),
            "consulted_experts_count": 0
        })
        self.workflow_step_started.emit("tool_gathering", "正在收集所需工具")
        self._consult_next_expert()

    def _consult_next_expert(self):
        """按顺序向专家列表中的下一个专家发起咨询"""
        ctx = self.execution_context
        if ctx["consulted_experts_count"] >= len(ctx["experts_to_consult"]):
            # Finished consulting all experts
            tool_names = list(ctx["recommended_tools"])
            self.workflow_step_finished.emit("tool_gathering", True,
                                             f"工具收集完成")
            self._start_chief_planning()
            return

        expert_name = ctx["experts_to_consult"][ctx["consulted_experts_count"]]
        expert_tools = self.expert_tool_definitions.get(expert_name, [])
        tool_briefs = [{"name": t["name"], "description": t["description"]} for t in expert_tools]

        topic = (f"【你的专属工具清单】\n{json.dumps(tool_briefs, ensure_ascii=False, indent=2)}\n\n"
                 f"【用户总体请求】\n{ctx['user_input']}")
        self.expert_task.set_topic(topic)
        self.expert_task.start()

    @pyqtSlot(str)
    def handle_expert_recommendation(self, expert_raw: str):
        """收集一位专家的工具推荐，并继续咨询下一位"""
        expert_json = extract_json_from_string(expert_raw)
        if expert_json:
            try:
                recommended_tool_names = json.loads(expert_json)
                self.execution_context["recommended_tools"].update(recommended_tool_names)
            except json.JSONDecodeError:
                pass  # Ignore malformed recommendations

        self.execution_context["consulted_experts_count"] += 1
        self._consult_next_expert()

    def _start_chief_planning(self):
        """所有专家咨询完毕后，启动总规划师"""
        ctx = self.execution_context
        tool_names = list(ctx["recommended_tools"])
        if not tool_names:
            self.error_signal.emit("Sorry, no suitable tools were found to handle your request.")
            return

        self.workflow_step_started.emit("planning", "制定最终执行方案...")

        final_tool_schemas = []
        all_defined_tools = [tool for tools in self.expert_tool_definitions.values() for tool in tools]
        for name in tool_names:
            for schema in all_defined_tools:
                if schema["name"] == name:
                    final_tool_schemas.append(schema)
                    break
        self.workflow_step_finished.emit("available_tools", True, f"共收集到 {len(all_defined_tools)} 个可用工具…")
        topic = (f"【项目可用工具集】\n{json.dumps(final_tool_schemas, ensure_ascii=False, indent=2)}\n\n"
                 f"【用户原始请求】\n{ctx['user_input']}")
        self.planner_task.set_topic(topic)
        self.planner_task.start()

    @pyqtSlot(str)
    def execute_workflow(self, workflow_raw: str):
        """接收到总规划师的工作流，由Python代码（执行器）执行"""
        workflow_json = extract_json_from_string(workflow_raw)
        if not workflow_json:
            self.workflow_step_finished.emit("planning", False,
                                             "Error: The planner failed to generate a valid workflow.")
            self.error_signal.emit("Aborting due to planning failure.")
            return
        try:
            workflow = json.loads(workflow_json)
            self.workflow_step_finished.emit("planning", True, f"执行方案制定完成，共 {len(workflow)} 步")
        except json.JSONDecodeError:
            self.workflow_step_finished.emit("planning", False,
                                             "Error: The planner generated invalid JSON for the workflow.")
            self.error_signal.emit("Aborting due to planning failure.")
            return

        self.execution_context.update({
            "workflow": workflow,
            "outputs": {},
            "current_step_index": 0
        })
        self.execute_next_step()

    def execute_next_step(self):
        """执行工作流中的下一步"""
        ctx = self.execution_context
        if ctx["current_step_index"] >= len(ctx["workflow"]):
            self.finished_signal.emit("All tasks have been completed!")
            return

        step = ctx["workflow"][ctx["current_step_index"]]
        tool_name = step.get("tool")
        description = step.get("description", f"Executing tool: {tool_name}")
        step_id = step.get("step_id", f"step_{ctx['current_step_index'] + 1}")

        self.workflow_step_started.emit(step_id, description)

        try:
            resolved_args = self._resolve_args(step.get("args", {}), ctx["outputs"])

            if tool_name and tool_name in self.MASTER_FUNCTION_MAP:
                func = self.MASTER_FUNCTION_MAP[tool_name]
                result = func(**resolved_args)

                ctx["outputs"][step_id] = result
                message = str(result.get("message", "No details provided."))

                if result.get("success"):
                    self.workflow_step_finished.emit(step_id, True, f"{message}")
                    ctx["current_step_index"] += 1
                    QTimer.singleShot(100, self.execute_next_step)
                else:
                    self.workflow_step_finished.emit(step_id, False, f"{message}")
                    self.error_signal.emit("任务执行失败，请检查日志")
            else:
                self.workflow_step_finished.emit(step_id, False, f"Error: Unknown tool '{tool_name}' specified.")
                self.error_signal.emit(f"Aborting: Unknown tool '{tool_name}'.")

        except Exception as e:
            self.workflow_step_finished.emit(step_id, False, f"An unexpected error occurred: {str(e)}")
            self.error_signal.emit(f"Aborting due to an unexpected error: {str(e)}")

    def _resolve_args(self, args: dict, outputs: dict) -> dict:
        # This function remains unchanged, it's correct.
        resolved_args = {}
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$outputs."):
                match = re.match(r"\$outputs\.([\w_]+)\.([\w_]+)(?:\[(\d+)\])?", value)
                if not match: raise ValueError(f"Invalid output reference format: {value}")
                ref_step_id, ref_key, ref_index = match.groups()
                if ref_step_id not in outputs: raise ValueError(f"Could not find output for step '{ref_step_id}'.")
                ref_value = outputs[ref_step_id].get(ref_key)
                if ref_index is not None:
                    if not isinstance(ref_value, list): raise ValueError(
                        f"Attempted to index a non-list result: {ref_key}")
                    try:
                        resolved_args[key] = ref_value[int(ref_index)]
                    except IndexError:
                        raise ValueError(f"Index out of range for: {value}")
                else:
                    resolved_args[key] = ref_value
            else:
                resolved_args[key] = value
        return resolved_args