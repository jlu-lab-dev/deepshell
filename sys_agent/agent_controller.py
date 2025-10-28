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
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match: return match.group(0)
    return None


class AgentController(QObject):
    update_signal = pyqtSignal(str)
    normal_update_signal = pyqtSignal(str)
    normal_finished_signal = pyqtSignal(str)
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
        self.fallback_chat_task.update_signal.connect(self.emit_normal_update)
        self.fallback_chat_task.complete_signal.connect(self.emit_normal_finished)

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
        self.emit_update("收到复杂指令，正在组建项目团队...")
        self.execution_context = {"user_input": user_input}

        topic = (f"【专家团队列表】\n{json.dumps(self.expert_briefs, ensure_ascii=False, indent=2)}\n\n"
                 f"【用户项目需求】\n{user_input}")
        self.pm_task.set_topic(topic)
        self.pm_task.start()

    @pyqtSlot(str)
    def handle_dispatch_result(self, dispatch_raw: str):
        """
        处理项目经理返回的专家列表。
        - 如果列表中只包含 fallback 专家，则进入聊天模式。
        - 否则，正常向列表中的所有专家分派任务。
        """
        logging.info(f"--- Raw Dispatcher Response ---:\n{dispatch_raw}\n---------------------------------")

        dispatch_json = extract_json_from_string(dispatch_raw)

        if not dispatch_json:
            error_msg = "错误：调度员返回了无效的格式（未能提取出JSON）。"
            logging.error(error_msg + f" Raw output was: {dispatch_raw}")
            self.emit_error(error_msg)
            return

        try:
            # 处理列表
            cleaned_json_str = dispatch_json.strip()
            selected_expert_names = json.loads(cleaned_json_str)

            if not isinstance(selected_expert_names, list):
                raise TypeError("Dispatcher response is not a list.")

        except (json.JSONDecodeError, TypeError) as e:
            error_msg = f"错误：无法将调度员的响应解析为专家列表。Error: {e}"
            logging.error(error_msg + f" Cleaned JSON was: {dispatch_json}")
            self.emit_error(error_msg)
            return

        # 情况一：列表为空，或只包含 fallback 专家 (处理闲聊和无法处理的任务)
        if not selected_expert_names or (
                len(selected_expert_names) == 1 and selected_expert_names[0] == "general_fallback_expert"):
            self.emit_update("正在准备回复...")
            user_input = self.execution_context.get("user_input")

            # 直接启动聊天Task
            self.fallback_chat_task.set_topic(user_input)
            self.fallback_chat_task.start()
            return  # 直接返回，跳过后续流程

        # 情况二：列表包含一个或多个需要使用工具的专家
        self.emit_update(f"团队组建完成：{', '.join(selected_expert_names)}。正在向各位专家征求工具建议...")

        self.execution_context.update({
            "experts_to_consult": selected_expert_names,
            "recommended_tools": set(),
            "consulted_experts_count": 0
        })
        self._consult_next_expert()

    def _consult_next_expert(self):
        """按顺序向专家列表中的下一个专家发起咨询"""
        ctx = self.execution_context
        if ctx["consulted_experts_count"] >= len(ctx["experts_to_consult"]):
            self._start_chief_planning()
            return

        expert_name = ctx["experts_to_consult"][ctx["consulted_experts_count"]]
        self.emit_update(f"正在咨询【{expert_name}】...")

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
                self.emit_update("一位专家未能提供有效建议（JSON格式错误），已跳过。")
        else:
            self.emit_update("一位专家未能提供有效建议，已跳过。")

        self.execution_context["consulted_experts_count"] += 1
        self._consult_next_expert()

    def _start_chief_planning(self):
        """所有专家咨询完毕后，启动总规划师"""
        ctx = self.execution_context
        tool_names = list(ctx["recommended_tools"])
        if not tool_names:
            self.emit_error("抱歉，所有专家均未推荐可用工具来完成您的请求。")
            return

        self.emit_update(f"工具收齐完毕：{', '.join(tool_names)}。正在制定最终工作流...")

        final_tool_schemas = []
        all_defined_tools = [tool for tools in self.expert_tool_definitions.values() for tool in tools]
        for name in tool_names:
            for schema in all_defined_tools:
                if schema["name"] == name:
                    final_tool_schemas.append(schema)
                    break

        topic = (f"【项目可用工具集】\n{json.dumps(final_tool_schemas, ensure_ascii=False, indent=2)}\n\n"
                 f"【用户原始请求】\n{ctx['user_input']}")
        self.planner_task.set_topic(topic)
        self.planner_task.start()

    @pyqtSlot(str)
    def execute_workflow(self, workflow_raw: str):
        """接收到总规划师的工作流，由Python代码（执行器）执行"""
        workflow_json = extract_json_from_string(workflow_raw)
        if not workflow_json:
            self.emit_error("错误：总规划师未能生成有效的工作流。")
            return
        try:
            workflow = json.loads(workflow_json)
        except json.JSONDecodeError:
            self.emit_error("错误：总规划师生成的工作流JSON格式无效。")
            return

        self.execution_context.update({
            "workflow": workflow,
            "outputs": {},
            "current_step_index": 0
        })
        self.execute_next_step()

    def execute_next_step(self):
        """执行工作流中的下一步（这部分就是纯代码的执行器）"""
        ctx = self.execution_context
        if ctx["current_step_index"] >= len(ctx["workflow"]):
            self.emit_finished("<br>---<br><b>所有任务已完成！</b>")
            return

        step = ctx["workflow"][ctx["current_step_index"]]
        tool_name = step.get("tool")
        args = step.get("args", {})
        description = step.get("description", f"执行工具: {tool_name}")

        self.emit_update(f"<br>---<br><b>正在执行步骤 {ctx['current_step_index'] + 1}:</b> {description}")

        try:
            resolved_args = self._resolve_args(args, ctx["outputs"])

            if tool_name and tool_name in self.MASTER_FUNCTION_MAP:
                func = self.MASTER_FUNCTION_MAP[tool_name]
                result = func(**resolved_args)

                step_id = step.get("step_id", f"step_{ctx['current_step_index'] + 1}")
                ctx["outputs"][step_id] = result

                status = "成功" if result.get("success") else "失败"
                message = str(result.get("message", "无信息"))
                self.emit_update(f"<br>状态: {status}<br>结果: {message}")

                if result.get("success"):
                    ctx["current_step_index"] += 1
                    QTimer.singleShot(100, self.execute_next_step)
                else:
                    self.emit_error("<br>---<br><b>任务因步骤失败而中止。</b>")
            else:
                self.emit_error(f"<br>错误：工作流指定了未知的工具 '{tool_name}'。")

        except Exception as e:
            self.emit_error(f"<br>执行步骤时发生意外错误: {str(e)}")

    def _resolve_args(self, args: dict, outputs: dict) -> dict:
        resolved_args = {}
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$outputs."):
                match = re.match(r"\$outputs\.([\w_]+)\.([\w_]+)(?:\[(\d+)\])?", value)
                if not match: raise ValueError(f"无效的输出引用格式: {value}")
                ref_step_id, ref_key, ref_index = match.groups()
                if ref_step_id not in outputs: raise ValueError(f"找不到步骤 '{ref_step_id}' 的输出。")
                ref_value = outputs[ref_step_id].get(ref_key)
                if ref_index is not None:
                    if not isinstance(ref_value, list): raise ValueError(f"试图对非列表类型的结果进行索引: {ref_key}")
                    try:
                        resolved_args[key] = ref_value[int(ref_index)]
                    except IndexError:
                        raise ValueError(f"索引超出范围: {value}")
                else:
                    resolved_args[key] = ref_value
            else:
                resolved_args[key] = value
        return resolved_args

    def emit_update(self, message: str):
        self.update_signal.emit(message)

    def emit_normal_update(self, message: str):
        self.normal_update_signal.emit(message)

    def emit_normal_finished(self, message: str):
        self.normal_finished_signal.emit(message)

    def emit_finished(self, message: str):
        self.finished_signal.emit(message)

    def emit_error(self, message: str):
        self.error_signal.emit(message)

