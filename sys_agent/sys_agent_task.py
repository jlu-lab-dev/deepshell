from chat.chat_task import ChatTask

class SysAgentExplanationTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='sys_agent_explanation')


class SysAgentFunctionCallTask(ChatTask):
    def __init__(self):
        super().__init__(assistant_type='sys_agent_function_call')
