# model_manager.py

import json
import logging
import re
from typing import Dict, Any, List, Generator
from langchain_community.chat_models import ChatTongyi, ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from config.config_manager import ConfigManager
from langchain_ollama import ChatOllama
from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory,
)
from langchain_core.runnables.history import RunnableWithMessageHistory
from utils.decorators import singleton
from chat.message_helpers import make_text_message
from langchain.chat_models.base import BaseChatModel


@singleton
class ModelManager:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.memory: Dict[str, BaseChatMessageHistory] = {}
        self.config_manager = ConfigManager()
        self.conversation_repo = None  # 懒加载，由 main_window 注入
        self.load_model_config()

    def load_model_config(self):
        """Initialize different LLM models based on configuration"""
        config = self.config_manager.model_config
        for model_name, model_config in config.items():
            model_type = model_config['type']
            
            if model_type == "aliyun":
                self.models[model_name] = ChatTongyi(
                    model=model_config['model_name'],
                    streaming=True,
                    api_key=model_config.get('api_key'),
                    temperature=model_config.get('temperature')
                )
            elif model_type == "deepseek":
                self.models[model_name] = ChatDeepSeek(
                    model=model_config['model_name'],
                    streaming=True,
                    api_key=model_config.get('api_key'),
                    temperature=model_config.get('temperature')
                )
            elif model_type == "ollama":
                self.models[model_name] = ChatOllama(
                    model=model_config['model_name'],
                    streaming=True,
                    api_key=model_config.get('api_key'),
                    base_url=model_config.get('api_base'),
                    temperature=model_config.get('temperature')
                )
            elif model_type in ["xunfei"]:
                self.models[model_name] = ChatOpenAI(
                    model=model_config['model_name'],
                    streaming=True,
                    api_key=model_config.get('api_key'),
                    base_url=model_config.get('api_base'),
                    temperature=model_config.get('temperature')
                )
    
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get configuration for a specific model or all models"""
        return self.config_manager.get_config(model_name)

    def get_model(self, model_name: str) -> BaseChatModel: 
        """Get a specific model by name"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        return self.models[model_name]

    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Get or create chat history for a session"""
        if session_id not in self.memory:
            self.memory[session_id] = InMemoryChatMessageHistory()
        return self.memory[session_id]
    
    def _prepare_messages(self, messages: List[str], system_prompt: str = None, session_id: str = 'default') -> List:
        """Convert string messages to LangChain message objects
        
        Args:
            messages: List of message strings to convert
            session_id: Session identifier to check if system prompt is needed
            system_prompt: Optional system prompt to use
        """
        result = []

        # Add system message if needed
        if self.memory.get(session_id) is None and system_prompt:
            # Whether the memory corresponding to session_id has been initialized determines 
            # whether the system prompt word needs to be added
            result.append(SystemMessage(content=system_prompt))
        
        # Add user messages
        for message in messages:
            result.append(HumanMessage(content=message))
            
        return result
    
    def set_conversation_repo(self, repo):
        """由 main_window 注入 ConversationRepository"""
        self.conversation_repo = repo

    def _get_chat_stream(self, model_name: str, messages: List[str], system_prompt: str = None, session_id: str = 'default'):
        """Common method to set up model, prepare messages and get response stream
        
        Args:
            model_name: Name of the model to use
            messages: List of message strings
            session_id: Identifier for the conversation session
            system_prompt: Optional system prompt to add at the beginning
            
        Returns:
            Response stream from the model
        """
        print("Using model: " + model_name)
        model = self.get_model(model_name)
        prepared_messages = self._prepare_messages(messages, system_prompt, session_id)
        
        conversation = RunnableWithMessageHistory(
            model, 
            lambda: self.get_session_history(session_id)
        )
        
        return conversation.stream(
            prepared_messages, 
            config={"configurable": {"session_id": session_id}}
        )
    
    def chat(self, model_name: str, messages: List[str], system_prompt: str = None, session_id: str = 'default') -> str:
        """Generate response using specified model
        
        Args:
            model_name: Name of the model to use
            messages: List of message strings
            session_id: Identifier for the conversation session
            system_prompt: Optional system prompt to add at the beginning
            
        Returns:
            String response from the model
        """
        response_stream = self._get_chat_stream(model_name, messages, system_prompt, session_id)
        
        response_text = ""
        for chunk in response_stream:
            response_text += chunk.content
            
        return response_text
    
    def chat_stream(self, model_name: str, messages: List[str], system_prompt: str = None, session_id: str = 'default', ) -> Generator[str, None, None]:
        """Generate streaming response using specified model

        Args:
            model_name: Name of the model to use
            messages: List of message strings
            session_id: Identifier for the conversation session
            system_prompt: Optional system prompt to add at the beginning

        Yields:
            Chunks of the response as they are generated
        """
        response_stream = self._get_chat_stream(model_name, messages, system_prompt, session_id)

        # Build the full response as we stream (for history)
        full_response = ""

        for chunk in response_stream:
            chunk_text = chunk.content
            full_response += chunk_text
            yield chunk_text

        # RunnableWithMessageHistory 在流式模式下不会自动将 AI 回复写入 InMemoryChatMessageHistory，
        # 需要手动补充，否则 _persist_stream_messages 读不到 AI 消息
        if full_response:
            history = self.get_session_history(session_id)
            history.add_ai_message(full_response)

        # 流结束后将本次对话消息追加写入数据库
        if self.conversation_repo and session_id:
            self._persist_stream_messages(session_id)

    def _persist_stream_messages(self, conversation_id: str):
        """将内存中最新一轮的消息（user + assistant）追加写入数据库（增量写入，分离字段）"""
        history = self.memory.get(conversation_id)
        if not history or not history.messages:
            return
        msgs_to_save = [m for m in history.messages if m.type in ("human", "ai")]
        if not msgs_to_save:
            return
        existing = self.conversation_repo.get_messages(conversation_id)
        existing_count = len(existing)
        if len(msgs_to_save) > existing_count:
            for msg in msgs_to_save[existing_count:]:
                role = "user" if msg.type == "human" else "assistant"
                raw_content = msg.content

                if role == "user":
                    user_input = raw_content
                    # 去掉 "用户输入：" 前缀
                    if user_input.startswith("用户输入："):
                        user_input = user_input[len("用户输入："):]
                    user_input = user_input.rstrip("\n")

                    # 提取 RAG 标记
                    relevant_docs = None
                    if "__RAG_DOCS_JSON__:" in raw_content:
                        user_input_clean, rag_block = raw_content.split("__RAG_DOCS_JSON__:", 1)
                        user_input_clean = user_input_clean.rstrip("\n")
                        if user_input_clean.startswith("用户输入："):
                            user_input_clean = user_input_clean[len("用户输入："):]
                        user_input_clean = user_input_clean.rstrip("\n")
                        try:
                            relevant_docs = json.loads(rag_block.strip())
                        except Exception:
                            relevant_docs = None
                        user_input = user_input_clean

                    # 提取 attachment_content（解析 "用户上传附件内容 N：" 段落）
                    attachment_content = []
                    att_matches = re.findall(
                        r"用户上传附件内容 \d+：(.*?)(?=\n\n|$)",
                        raw_content, re.DOTALL
                    )
                    for att_text in att_matches:
                        attachment_content.append({"content": att_text.strip()})

                    content = make_text_message(
                        role="user",
                        user_input=user_input,
                        attachment_content=attachment_content or None,
                        relevant_docs=relevant_docs,
                    )

                else:
                    content = make_text_message(role="assistant", user_input=raw_content)

                self.conversation_repo.add_message(conversation_id, role, content)
        self.conversation_repo.update_timestamp(conversation_id)


if __name__ == "__main__":
    model_manager = ModelManager()
    # print(f"test DeepSeek-V3: {model_manager.chat('DeepSeek-V3', ['你是谁', '我刚才和你说了什么'])}")
    # print(f"test DeepSeek-R1: {model_manager.chat('DeepSeek-R1', ['你是谁'])}")
    print(f"test Qwen-Max: {model_manager.chat('Qwen-Max', ['你是谁', '我刚才和你说了什么'])}")
    # print(f"test Ollama-Qwen-0.5B: {model_manager.chat('Ollama-Qwen-0.5B', ['你是谁', '我刚才和你说了什么'])}")

    model_manager = ModelManager()
    model_name = "Qwen-Max"

    print(f"开始与 {model_name} 进行对话，输入 'exit' 退出。")
    while True:
        user_input = input("你: ")
        if user_input.lower() == "exit":
            print("对话结束。")
            break
        print(f"{model_name}: ", end="", flush=True)
        
        for chunk in model_manager.chat_stream(model_name, [user_input], session_id="test"):
            print(chunk, end="", flush=True)
        print()

