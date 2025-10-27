import json
import re
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

from sys_agent.sys_agent_task import WorkflowPlannerTask, WorkflowExecutorTask, ToolRouterTask
from sys_agent.toolkit_sys import FUNCTION_MAP, get_function_schemas, get_tool_briefs


def extract_json_from_string(text):
    """
    从可能包含Markdown标记或其他文本的字符串中提取出第一个有效的JSON对象或数组。
    """
    # 寻找第一个 '{' 或 '['，这是JSON的开始
    first_brace = text.find('{')
    first_bracket = text.find('[')

    if first_brace == -1 and first_bracket == -1:
        return None  # 没有找到任何JSON的起始符号

    # 确定JSON是从 '{' 开始还是从 '[' 开始
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_char = '{'
        end_char = '}'
        start_index = first_brace
    else:
        start_char = '['
        end_char = ']'
        start_index = first_bracket

    # 从起始位置开始，寻找与之匹配的结束符号
    # 这是一个简化的匹配，对于复杂的嵌套JSON可能不够完美，但对大多数情况有效
    # 更稳健的方法是使用正则表达式
    # 使用正则表达式查找被 `[]` 或 `{}` 包围的最外层内容
    match = re.search(r'(\{.*\}|\[.*\])', text[start_index:], re.DOTALL)
    if match:
        return match.group(0)

    return None  # 如果正则没有匹配到，则返回None


class AgentController(QObject):
    """
    负责处理所有与AI Agent相关的业务逻辑，与UI完全分离。
    通过信号与主窗口通信。
    """
    # --- 定义信号 ---
    update_signal = pyqtSignal(str)  # 用于发送增量更新的文本
    finished_signal = pyqtSignal(str)  # 用于发送工作流成功结束的消息
    error_signal = pyqtSignal(str)  # 用于发送错误信息

    def __init__(self):
        super().__init__()
        # 【修改】初始化三个智能体
        self.router_task = ToolRouterTask()
        self.planner_task = WorkflowPlannerTask()
        self.executor_task = WorkflowExecutorTask()

        # 【修改】连接各自的信号到处理函数
        self.router_task.complete_signal.connect(self.handle_router_result)
        self.planner_task.complete_signal.connect(self.execute_plan)
        self.executor_task.complete_signal.connect(self.handle_executor_result)

        # 【修改】加载并缓存两种工具描述
        try:
            self.tool_briefs = get_tool_briefs()  # 用于路由
            full_schemas_str = get_function_schemas()
            self.full_function_schemas = json.loads(full_schemas_str)  # 用于规划
        except Exception as e:
            self.tool_briefs = []
            self.full_function_schemas = []
            print(f"CRITICAL ERROR: Failed to load tools. Error: {e}")

        self.execution_context = {}

    @pyqtSlot(str)
    def start_workflow(self, user_input: str):
        """工作流的公共入口点，现在启动的是路由阶段。"""
        self.emit_update("收到指令，正在分析所需工具...")
        self.execution_context = {"user_input": user_input}  # 存储用户原始输入

        # --- 阶段一：路由 ---
        topic_with_context = (
            f"【可用工具清单】\n"
            f"{json.dumps(self.tool_briefs, ensure_ascii=False, indent=2)}\n\n"
            f"【用户请求】\n"
            f"{user_input}"
        )
        self.router_task.set_topic(topic_with_context)
        self.router_task.start()

    @pyqtSlot(str)
    def handle_router_result(self, selected_tools_raw: str):
        """处理路由结果，筛选工具，然后启动规划阶段。"""
        self.emit_update("工具分析完成，正在为您制定执行计划...")

        selected_tools_json = extract_json_from_string(selected_tools_raw)
        if not selected_tools_json:
            self.emit_error("错误：工具路由智能体返回了无效的格式。")
            return

        try:
            selected_tool_names = json.loads(selected_tools_json)
            if not isinstance(selected_tool_names, list):
                raise json.JSONDecodeError("Not a list", selected_tools_json, 0)
        except json.JSONDecodeError:
            self.emit_error("错误：工具路由结果不是一个有效的工具名称列表。")
            return

        if not selected_tool_names:
            self.emit_error("抱歉，根据您的请求，没有找到可以使用的工具。")
            return

        # --- 筛选详细的工具Schema ---
        filtered_schemas = [
            schema for schema in self.full_function_schemas
            if schema.get("name") in selected_tool_names
        ]
        filtered_schemas_str = json.dumps(filtered_schemas, ensure_ascii=False, indent=2)

        # --- 阶段二：规划 ---
        user_input = self.execution_context.get("user_input")
        topic_with_context = (
            f"【可用工具】\n"
            f"{filtered_schemas_str}\n\n"
            f"【用户请求】\n"
            f"{user_input}"
        )
        self.planner_task.set_topic(topic_with_context)
        self.planner_task.start()

    @pyqtSlot(str)
    def execute_plan(self, plan_raw_output: str):
        # ... (此函数及之后的所有函数，包括 execute_next_step 和 handle_executor_result，都【保持不变】) ...
        # ... 因为它们只关心“计划”本身，不关心计划是怎么来的。
        plan_json_str = extract_json_from_string(plan_raw_output)
        if not plan_json_str:
            self.emit_error("错误：未能从模型返回内容中提取出有效的计划。")
            return
        try:
            plan = json.loads(plan_json_str)
            if not isinstance(plan, list) or not plan:
                self.emit_error("抱歉，我无法为您的请求制定计划。")
                return
        except json.JSONDecodeError:
            self.emit_error("错误：返回了无效的计划格式。")
            return
        plan_text = "<br>---<br><b>执行计划：</b><br>" + "<br>".join(
            [f"{item.get('step', i + 1)}. {item.get('description', 'N/A')}" for i, item in enumerate(plan)])
        self.emit_update(plan_text)
        self.execution_context.update({
            "plan": plan,
            "results": [],
            "current_step_index": 0
        })
        self.execute_next_step()

    def execute_next_step(self):
        ctx = self.execution_context
        if ctx["current_step_index"] >= len(ctx["plan"]):
            self.emit_finished("<br>---<br><b>所有任务已完成！</b>")
            return
        current_step = ctx["plan"][ctx["current_step_index"]]
        update_msg = f"<br>---<br><b>正在执行步骤 {current_step.get('step', '?')}:</b> {current_step.get('description', '...')}"
        self.emit_update(update_msg)
        executor_context = {
            "overall_plan": ctx["plan"],
            "tool_results": ctx["results"],
            "current_step_description": current_step.get("description")
        }
        # 【注意】执行者也只看到筛选后的工具，这没问题，因为它只需要调用计划中指定的工具
        # 为保持一致性，我们依然可以只提供筛选后的工具列表
        selected_tool_names = {step.get("tool") for step in ctx["plan"] if step.get("tool")}
        filtered_schemas = [
            schema for schema in self.full_function_schemas
            if schema.get("name") in selected_tool_names
        ]
        filtered_schemas_str = json.dumps(filtered_schemas, ensure_ascii=False, indent=2)
        topic_with_context = (
            f"【可用工具】\n"
            f"{filtered_schemas_str}\n\n"
            f"【上下文信息】\n"
            f"{json.dumps(executor_context, ensure_ascii=False, indent=2)}"
        )
        self.executor_task.set_topic(topic_with_context)
        self.executor_task.start()

    @pyqtSlot(str)
    def handle_executor_result(self, tool_call_json: str):
        ctx = self.execution_context
        current_step = ctx["plan"][ctx["current_step_index"]]
        clean_json_str = extract_json_from_string(tool_call_json)
        if not clean_json_str:
            self.emit_error(f"<br>错误：执行者返回了无效的工具调用格式。")
            return
        try:
            tool_call = json.loads(clean_json_str)
            tool_name = tool_call.get("tool")
            args = tool_call.get("args", {})
            if tool_name and tool_name in FUNCTION_MAP:
                func = FUNCTION_MAP[tool_name]
                result = func(**args)
                ctx["results"].append({"step": current_step.get("step"), "output": result})
                status = "成功" if result.get("success") else "失败"
                message = str(result.get("message", "无返回信息"))
                result_msg = f"<br>状态: {status}<br>结果: {message}"
                self.emit_update(result_msg)
                if result.get("success"):
                    ctx["current_step_index"] += 1
                    self.execute_next_step()
                else:
                    self.emit_error("<br>---<br><b>任务因步骤失败而中止。</b>")
            else:
                self.emit_error(f"<br>错误：无法为此步骤生成有效的工具调用或找不到工具 '{tool_name}'。")
        except Exception as e:
            self.emit_error(f"<br>执行时发生意外错误: {str(e)}")

    # --- 封装信号发射的辅助方法 ---
    def emit_update(self, message: str):
        self.update_signal.emit(message)

    def emit_finished(self, message: str):
        self.finished_signal.emit(message)

    def emit_error(self, message: str):
        self.error_signal.emit(message)
