# assistant.py

import logging
import uuid

from typing import Optional, Tuple

from config.config_manager import ConfigManager
from chat.model_manager import ModelManager
from rag.rag_manager import RAGManager
from rag.page_context import expand_pdf_page_context
from chat.rag_citations import make_citation_docs, make_citation_prompt
from database.repository.knowledge_base_repository import KnowledgeBaseRepository

class Assistant:
    def __init__(self, assistant_type: str, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.model_manager = ModelManager()
        self.rag_manager = RAGManager()
        self.web_search_manager = None
        self.last_rag_docs = []
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

    def _retrieve_rag_docs(self, user_input: str) -> list:
        """聊天与 Agent 共用 Top-3 检索、同页扩展和真实来源转换。"""
        if not self.kb_list:
            return []
        results = self.rag_manager.search(user_input, k=3, knowledge_bases=self.kb_list)
        page_cfg = self.rag_manager.config.get("page_context", {})
        if page_cfg.get("enabled", False):
            original_count = len(results)
            results = expand_pdf_page_context(
                vector_db=self.rag_manager.vector_db,
                results=results,
                knowledge_bases=self.kb_list,
                max_pages=int(page_cfg.get("max_pages", 1)),
                max_added_chunks=int(page_cfg.get("max_added_chunks", 12)),
                max_total_chars=int(page_cfg.get("max_total_chars", 2500)),
            )
            logging.info(
                "[ASSISTANT] 原始检索 %d 个 Chunk，同页扩展后 %d 个 Chunk",
                original_count, len(results),
            )
        kb_names = {str(kb.id): kb.name for kb in KnowledgeBaseRepository().list_knowledge_bases()}
        return make_citation_docs(results, kb_names)

    def build_rag_enriched_message(self, user_input: str) -> Tuple[str, list]:
        """为普通聊天、流式聊天和 Agent 首轮构建统一的编号证据及来源元数据。"""
        docs = self._retrieve_rag_docs(user_input)
        if not self.kb_list:
            return user_input, docs
        if docs:
            evidence = make_citation_prompt(docs)
            return (
                f"{user_input}\n\n请仅依据以下检索证据回答。"
                "使用 [1]、[2] 等编号引用对应证据。只能引用实际提供的编号，"
                "证据不足时请明确说明，不能编造文档或页码。\n\n"
                f"{evidence}",
                docs,
            )
        return (
            f"{user_input}\n\n当前选中知识库没有返回相关证据。"
            "请说明未检索到依据，不要虚构文档来源。",
            docs,
        )

    def chat(self, messages: list[str]) -> str:
        messages = list(messages)
        self.last_rag_docs = []
        messages[-1], self.last_rag_docs = self.build_rag_enriched_message(messages[-1])
        return self.model_manager.chat(
            model_name=self.model,
            messages=messages,
            system_prompt=self.prompt_template,
            session_id=self.session_id,
        )

    def chat_stream(self, messages: list[str]):
        """检索真实证据，构建带引用编号的上下文，并独立缓存历史来源。"""
        original_input = messages[-1]
        messages = list(messages)
        self.last_rag_docs = []
        messages[-1], self.last_rag_docs = self.build_rag_enriched_message(original_input)
        self.model_manager.set_pending_rag_turn(
            self.session_id, original_input, self.last_rag_docs
        )
        return self.model_manager.chat_stream(
            model_name=self.model,
            messages=messages,
            system_prompt=self.prompt_template,
            session_id=self.session_id,
        )

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
