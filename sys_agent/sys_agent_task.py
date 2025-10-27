from chat.chat_task import ChatTask


class ToolRouterTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='tool_router')


class WorkflowPlannerTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='workflow_planner')


class WorkflowExecutorTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='workflow_executor')



