# model_manager.py

import json
import logging
import re
import threading
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
from langchain_core.messages import AIMessageChunk
from langchain_core.runnables.history import RunnableWithMessageHistory
from utils.decorators import singleton
from chat.message_helpers import make_text_message, parse_message_content, is_compressed
from langchain.chat_models.base import BaseChatModel


@singleton
class ModelManager:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.memory: Dict[str, BaseChatMessageHistory] = {}
        self.config_manager = ConfigManager()
        self.conversation_repo = None  # 懒加载，由 main_window 注入
        self.load_model_config()

        # ── 压缩控制 ──
        self._compressing: set = set()                     # 正在异步压缩的 session_id
        self._compress_locks: Dict[str, threading.Lock] = {}  # 每个 session 一把锁

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
            lambda sid: self.get_session_history(sid)
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

        # 注意：RunnableWithMessageHistory.stream() 会自动将 user 和 AI 写入历史，
        # 但写入的 AI 类型是 AIMessageChunk（type="AIMessageChunk"）而非 AIMessage（type="ai"）。
        # 不能再手动 add_ai_message，否则 AI 消息会双份，导致 LLM 上下文膨胀、输出重复。
        # _persist_stream_messages 已做适配，能正确识别 AIMessageChunk 并持久化。
        # if full_response:
        #     history = self.get_session_history(session_id)
        #     history.add_ai_message(full_response)  # ← 禁止！会导致 AI 消息双份

        # 流结束后将本次对话消息追加写入数据库
        if self.conversation_repo and session_id:
            # 如果该 session 正在异步压缩中，先等压缩完成再 persist，防止竞态
            self._wait_for_compress(session_id)
            self._persist_stream_messages(session_id)
            # 异步触发压缩检查（后台线程，不阻塞用户）
            self._start_async_compress(session_id)

    # ── 异步压缩控制 ──────────────────────────────────────────────────────

    def _get_compress_lock(self, session_id: str) -> threading.Lock:
        """获取（或创建）某个 session 的压缩锁。"""
        if session_id not in self._compress_locks:
            self._compress_locks[session_id] = threading.Lock()
        return self._compress_locks[session_id]

    def _wait_for_compress(self, session_id: str):
        """如果该 session 正在异步压缩，阻塞等待完成。"""
        if session_id in self._compressing:
            lock = self._get_compress_lock(session_id)
            lock.acquire()
            lock.release()
            logging.info(f"[ModelManager] Waited for compression to finish: {session_id[:8]}..")

    def _start_async_compress(self, session_id: str):
        """在后台线程启动压缩检查。已在压缩中则等待完成。"""
        if session_id in self._compressing:
            # 该 session 正在异步压缩中，等它完成（防止压缩重建内存时吞掉新消息）
            self._wait_for_compress(session_id)
            return
        self._compressing.add(session_id)
        lock = self._get_compress_lock(session_id)
        t = threading.Thread(
            target=self._run_compress,
            args=(session_id, lock),
            daemon=True,
            name=f"compress-{session_id[:8]}",
        )
        t.start()

    def _run_compress(self, session_id: str, lock: threading.Lock):
        """后台线程：执行压缩 → 持锁重建内存。"""
        try:
            lock.acquire()
            from chat.memory_compressor import MemoryCompressor
            MemoryCompressor().maybe_compress(session_id, self.conversation_repo)
        except Exception as e:
            logging.error(f"[ModelManager] Async compression error: {e}")
        finally:
            self._compressing.discard(session_id)
            lock.release()

    def _persist_stream_messages(self, conversation_id: str):
        """将内存中最新一轮的消息（user + assistant）追加写入数据库（增量写入，分离字段）"""
        history = self.memory.get(conversation_id)
        if not history or not history.messages:
            return
        # RunnableWithMessageHistory.stream() 写入历史的 AI 消息类型是 AIMessageChunk（type="AIMessageChunk"）
        # 而非 AIMessage（type="ai"），需要同时识别两者
        msgs_to_save = [m for m in history.messages if m.type in ("human", "ai") or isinstance(m, AIMessageChunk)]
        if not msgs_to_save:
            return
        existing = self.conversation_repo.get_messages(conversation_id)
        # 只统计活跃消息（排除已压缩和 summary），否则压缩后计数永远大于内存
        existing_count = sum(
            1 for m in existing
            if not is_compressed(m.content)
            and parse_message_content(m.content).get("type") != "summary"
            and m.role in ("user", "assistant")
        )
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

