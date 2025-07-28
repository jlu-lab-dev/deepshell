import uuid

from typing import Optional

from config.config_manager import ConfigManager
from chat.model_manager import ModelManager
from rag.rag_manager import RAGManager
from chat.web_search_manager import WebSearchManager
from sys_agent.sys_func_call import get_function_schemas

class Assistant:
    def __init__(self, assistant_type: str, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.model_manager = ModelManager()
        self.rag_manager = RAGManager()
        self.web_search_manager = WebSearchManager(is_enabled=False)
        self._load_assistant_config(assistant_type)

    def _load_assistant_config(self, assistant_type: str) -> None:
        """Load assistant configuration from YAML file."""
        assistant_config = ConfigManager().get_assistant_config(assistant_type)
        self.type = assistant_type
        self.name = assistant_config.get("name", "Assistant")
        self.description = assistant_config.get("description", "A helpful assistant.")
        self.kb_list = []
        self.prompt_template = assistant_config.get("prompt_template", "You are a helpful assistant.")
        self.model = assistant_config.get("model", "DeepSeek-V3")

        # 动态插入 function_schemas
        if assistant_type == "sys_agent_function_call" or assistant_type == "sys_agent_explanation":
            self.prompt_template = self.prompt_template.replace(
                "{function_schemas}", get_function_schemas()
            )

    def chat(self, messages: list[str]) -> str:
        import logging
        
        enhanced_message = messages[-1]
        context_parts = []
        
        logging.info(f"[ASSISTANT] 开始处理查询: '{messages[-1]}'")
        
        # 使用 RAG 模式，将知识库搜索结果注入
        if len(self.kb_list):
            logging.info(f"[ASSISTANT] 使用知识库: {self.kb_list}")
            knowledge = self.rag_manager.get_relevant_context(messages[-1], knowledge_bases=self.kb_list)
            context_parts.append(f"知识库信息：\n{knowledge}")
        
        # 检查是否需要网络搜索
        if self.web_search_manager.is_search_query(messages[-1]):
            logging.info(f"[ASSISTANT] 查询被识别为需要网络搜索")
            web_context = self.web_search_manager.get_search_context(messages[-1])
            if web_context and web_context != "未找到相关的网络搜索结果。":
                logging.info(f"[ASSISTANT] 网络搜索成功，将结果注入上下文")
                context_parts.append(f"网络搜索结果：\n{web_context}")
            else:
                logging.warning(f"[ASSISTANT] 网络搜索未返回有效结果")
        else:
            logging.info(f"[ASSISTANT] 查询未被识别为需要网络搜索")
        
        # 如果有上下文信息，则添加到消息中
        if context_parts:
            context_text = "\n\n".join(context_parts)
            enhanced_message = f"{messages[-1]}\n\n参考以下信息回答用户问题：\n{context_text}"
            messages[-1] = enhanced_message
            logging.info(f"[ASSISTANT] 上下文增强完成，总长度: {len(context_text)} 字符")
        else:
            logging.info(f"[ASSISTANT] 无额外上下文，使用原始查询")
        
        return self.model_manager.chat(
            model_name=self.model,
            messages=messages,
            system_prompt=self.prompt_template,
            session_id=self.session_id
        )

    def chat_stream(self, messages: list[str]):
        import logging
        
        enhanced_message = messages[-1]
        context_parts = []
        
        logging.info(f"[ASSISTANT_STREAM] 开始处理流式查询: '{messages[-1]}'")
        
        # 使用 RAG 模式，将知识库搜索结果注入
        if len(self.kb_list):
            logging.info(f"[ASSISTANT_STREAM] 使用知识库: {self.kb_list}")
            knowledge = self.rag_manager.get_relevant_context(messages[-1], knowledge_bases=self.kb_list)
            context_parts.append(f"知识库信息：\n{knowledge}")
        
        # 检查是否需要网络搜索
        if self.web_search_manager.is_search_query(messages[-1]):
            logging.info(f"[ASSISTANT_STREAM] 查询被识别为需要网络搜索")
            web_context = self.web_search_manager.get_search_context(messages[-1])
            if web_context and web_context != "未找到相关的网络搜索结果。":
                logging.info(f"[ASSISTANT_STREAM] 网络搜索成功，将结果注入上下文")
                context_parts.append(f"网络搜索结果：\n{web_context}")
            else:
                logging.warning(f"[ASSISTANT_STREAM] 网络搜索未返回有效结果")
        else:
            logging.info(f"[ASSISTANT_STREAM] 查询未被识别为需要网络搜索")
        
        # 如果有上下文信息，则添加到消息中
        if context_parts:
            context_text = "\n\n".join(context_parts)
            enhanced_message = f"{messages[-1]}\n\n参考以下信息回答用户问题：\n{context_text}"
            messages[-1] = enhanced_message
            logging.info(f"[ASSISTANT_STREAM] 上下文增强完成，总长度: {len(context_text)} 字符")
        else:
            logging.info(f"[ASSISTANT_STREAM] 无额外上下文，使用原始查询")

        return self.model_manager.chat_stream(
            model_name=self.model,
            messages=messages,
            system_prompt=self.prompt_template,
            session_id=self.session_id
        )

    def set_selected_kb(self, selected_kb_id_list: list[int]):
        self.kb_list = selected_kb_id_list

    def switch_model(self, model_name):
        self.model = model_name
    
    def enable_web_search(self, enabled: bool = True):
        """启用或禁用网络搜索功能"""
        self.web_search_manager.set_enabled(enabled)
    
    def get_web_search_engines(self):
        """获取可用的搜索引擎列表"""
        return self.web_search_manager.get_available_engines()


if __name__ == "__main__":
    def test_assistant_and_session():
        assistant = Assistant("general")
        first_assistant = assistant.session_id
        messages = ["你是谁"]
        response = assistant.chat(messages)
        print(response)
        messages = ["你的 system_prompt 是什么"]
        response = assistant.chat(messages)
        print(response)
        messages = ["我是小明"]
        response = assistant.chat(messages)
        print(response)
        # 测试session，assistant 应该记得我是谁 
        messages = ["我是谁"]
        response = assistant.chat(messages)
        print(response)
        
        # 测试session，创建了新的 assistant 他应该不记得我是谁 
        assistant = Assistant("general")
        messages = ["我是谁"]
        response = assistant.chat(messages)
        print(response)

        # 测试session，使用第一个 assistant 的 session 创建 assitant 它应该记得我是谁
        assistant = Assistant("general", first_assistant)
        messages = ["我是谁"]
        response = assistant.chat(messages)
        print(response)


    def test_stream():
        # 流式对话测试
        assistant = Assistant("general")
        print(f"开始与 {assistant.name} 进行对话，输入 'exit' 退出。")
        while True:
            user_input = input("你: ")
            if user_input.lower() == "exit":
                print("对话结束。")
                break
            print(f"{assistant.model}: ", end="", flush=True)
            
            for chunk in assistant.chat_stream([user_input]):
                print(chunk, end="", flush=True)
            print()

    def test_rag():
        assistant = Assistant("knowledgebase")
        assistant.rag_manager.add_document("../rag/test.txt")
        # print(assistant.rag_manager.get_document_count())
        print(assistant.chat(["吉林大学"]))
        # print(assistant.chat(["你知道方德吗"]))
    # test_assistant_and_session()
    test_rag()