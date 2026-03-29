# assistant.py

import uuid

from typing import Optional, Tuple

from config.config_manager import ConfigManager
from chat.model_manager import ModelManager
from rag.rag_manager import RAGManager

class Assistant:
    def __init__(self, assistant_type: str, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.model_manager = ModelManager()
        self.rag_manager = RAGManager()
        self.web_search_manager = None
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
        import json

        enhanced_message = messages[-1]
        context_parts = []
        rag_docs = []   # RAG 结构化结果，供后续持久化

        logging.info(f"[ASSISTANT_STREAM] 开始处理流式查询: '{messages[-1]}'")

        # 使用 RAG 模式，将知识库搜索结果注入
        if len(self.kb_list):
            logging.info(f"[ASSISTANT_STREAM] 使用知识库: {self.kb_list}")
            # 调用 search 获取结构化结果
            rag_results = self.rag_manager.search(messages[-1], k=3, knowledge_bases=self.kb_list)
            if rag_results:
                for i, result in enumerate(rag_results):
                    source = result.get('metadata', {}).get('source', 'Unknown')
                    content_text = result.get('content', '')
                    rag_docs.append({"source": source, "content": content_text})
                    context_parts.append(f"[Document {i+1}] (Source: {source})\n{content_text}")
                knowledge = "\n\n".join(context_parts)
                context_parts = [f"知识库信息：\n{knowledge}"]
            else:
                context_parts = []
                logging.info(f"[ASSISTANT_STREAM] 知识库未返回有效结果")

        # 如果有上下文信息，则添加到消息中
        if context_parts:
            context_text = "\n\n".join(context_parts)
            enhanced_message = f"{messages[-1]}\n\n参考以下信息回答用户问题：\n{context_text}"
            messages[-1] = enhanced_message
            logging.info(f"[ASSISTANT_STREAM] 上下文增强完成，总长度: {len(context_text)} 字符")
        else:
            logging.info(f"[ASSISTANT_STREAM] 无额外上下文，使用原始查询")

        # 附加 RAG 结构化结果标记，供 model_manager 在持久化时提取
        if rag_docs:
            messages[-1] = messages[-1] + f"\n__RAG_DOCS_JSON__:{json.dumps(rag_docs, ensure_ascii=False)}\n"

        return self.model_manager.chat_stream(
            model_name=self.model,
            messages=messages,
            system_prompt=self.prompt_template,
            session_id=self.session_id
        )

    def build_rag_enriched_message(self, user_input: str) -> Tuple[str, list]:
        """同步构建带 RAG 上下文的用户消息（用于 Agent 首轮调用）。

        与 chat_stream 不同，此方法不调用 LLM，仅完成 RAG 检索并返回增强文本。

        Returns:
            enriched_text: 带 RAG 上下文的字符串（供 LLM 使用）
            rag_docs: [{source, content}]（供持久化用）
        """
        import logging
        import json

        context_parts = []
        rag_docs = []

        logging.info(f"[ASSISTANT_RAG] 开始 RAG 增强: '{user_input}'")

        if len(self.kb_list):
            logging.info(f"[ASSISTANT_RAG] 使用知识库: {self.kb_list}")
            rag_results = self.rag_manager.search(user_input, k=3, knowledge_bases=self.kb_list)
            if rag_results:
                for result in rag_results:
                    source = result.get('metadata', {}).get('source', 'Unknown')
                    content_text = result.get('content', '')
                    rag_docs.append({"source": source, "content": content_text})
                    context_parts.append(f"[Document] (Source: {source})\n{content_text}")

        if context_parts:
            context_text = "参考以下信息回答用户问题：\n" + "\n\n".join(context_parts)
            enriched_text = f"{user_input}\n\n{context_text}"
            logging.info(f"[ASSISTANT_RAG] RAG 增强完成，共 {len(rag_docs)} 个文档")
        else:
            enriched_text = user_input
            logging.info(f"[ASSISTANT_RAG] 无 RAG 结果，使用原始查询")

        return enriched_text, rag_docs

    def set_selected_kb(self, selected_kb_id_list: list[int]):
        self.kb_list = selected_kb_id_list

    def switch_model(self, model_name):
        self.model = model_name

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
        # print(assistant.chat(["你知道DeepShell吗"]))
    # test_assistant_and_session()
    test_rag()