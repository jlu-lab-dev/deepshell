from usr.share.aiassistant.config.config_manager import ConfigManager
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from typing import Dict, List


def log_func(message):
    print(message)


def handle_exception_func(message):
    print("Error:", message)


class MindMapWork:
    def __init__(self, config: Dict):
        self.llm = ChatOpenAI(
            model=config["model_name"],
            api_key=config["api_key"],
            base_url=config["api_base"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
        )

        # 思维导图生成提示模板
        self.MINDMAP_PROMPT = PromptTemplate.from_template("""
        请将以下需求转换为结构化思维导图内容，使用Markdown列表格式表示层级关系：

        需求：{input}

        输出要求：
        1. 层级不超过5级
        2. 每行以'-'开头
        3. 使用空格表示缩进层级
        示例：
        - 中心主题
          - 分支主题1
            - 子主题1.1
          - 分支主题2
        """)

    def generation_chain(self):
        """构建处理链式"""
        return (
                RunnablePassthrough()
                | self.MINDMAP_PROMPT
                | self.llm
                | RunnableLambda(lambda x: x.content)
        )


if __name__ == "__main__":
    # 配置加载
    config_manager = ConfigManager()
    config = config_manager.get_model_config('Qwen-PLUS')

    # 初始化工作流
    mindmap_work = MindMapWork(config)

    # 执行生成链
    chain = mindmap_work.generation_chain()
    result = chain.invoke("请生成关于高中物理知识的思维导图")
    print(result)
