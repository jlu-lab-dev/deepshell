from chat.chat_task import ChatTask


class ProjectManagerTask(ChatTask):
    """项目经理，负责选择专家团队"""
    def __init__(self):
        # 对应 prompts/project_manager.yaml
        super().__init__(assistant_type='project_manager')

class ExpertToolRecommenderTask(ChatTask):
    """领域专家，负责推荐自己领域内的工具"""
    def __init__(self):
        # 对应 prompts/expert_tool_recommender.yaml
        super().__init__(assistant_type='expert_tool_recommender')

class ChiefPlannerTask(ChatTask):
    """总规划师，负责制定最终的跨领域工作流"""
    def __init__(self):
        # 对应 prompts/chief_planner.yaml
        super().__init__(assistant_type='chief_planner')



