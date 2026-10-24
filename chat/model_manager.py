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
        self._pending_rag_turn = {}
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
            elif model_type in ["xunfei", "openai_compatible"]:
                api_base = model_config.get('api_base') or ''
                api_key = model_config.get('api_key') or ''
                if model_type == "openai_compatible" and (
                    not api_base.strip() or not api_key.strip()
                    or api_base.startswith('${') or api_key.startswith('${')
                ):
                    logging.warning("Model %s needs LLM_BASE_URL and ALIYUN_API_KEY in config/.env", model_name)
                    continue
                self.models[model_name] = ChatOpenAI(
                    model=model_config['model_name'],
                    streaming=True,
                    api_key=model_config.get('api_key'),
                    base_url=model_config.get('api_base'),
                    temperature=model_config.get('temperature'),
                    max_tokens=model_config.get('max_tokens') if model_type == 'openai_compatible' else None
                )
    
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get configuration for a specific model or all models"""
        return self.config_manager.get_config(model_name)

    def get_model(self, model_name: str) -> BaseChatModel: 
        """Get a specific model by name"""
        if model_name not in self.models:
            if self.config_manager.model_config.get(model_name, {}).get('type') == 'openai_compatible':
                raise ValueError(f"Model {model_name} needs LLM_BASE_URL and ALIYUN_API_KEY in config/.env")
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
    
    def set_pending_rag_turn(self, session_id: str, original_input: str, docs: list):
        """独立缓存本轮原始问题和真实来源，不向 Prompt 拼接内部 JSON 标记。"""
        self._pending_rag_turn[session_id] = {
            "original_input": original_input,
            "relevant_docs": list(docs),
        }

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
    
    def chat_once(self, model_name: str, messages: List[str], system_prompt: str = None, session_id=None) -> str:
        """Agent 已提供完整上下文；不再用 RunnableWithMessageHistory 重复累积。"""
        prepared = ([SystemMessage(content=system_prompt)] if system_prompt else [])
        prepared.extend(HumanMessage(content=message) for message in messages)
        return ''.join(chunk.content for chunk in self.get_model(model_name).stream(prepared))

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
        try:
            response_stream = self._get_chat_stream(model_name, messages, system_prompt, session_id)
            for chunk in response_stream:
                yield chunk.content

            # RunnableWithMessageHistory 已保存 user 和 AIMessageChunk，不重复添加 AI 消息。
            if self.conversation_repo and session_id:
                self._wait_for_compress(session_id)
                self._persist_stream_messages(session_id)
                self._start_async_compress(session_id)
        finally:
            # 包含异常、中断和未启用持久化的情况，避免下一轮误用残留来源。
            self._pending_rag_turn.pop(session_id, None)

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
        pending = self._pending_rag_turn.get(conversation_id)
        latest_human = next(
            (msg for msg in reversed(msgs_to_save) if msg.type == "human"), None
        )
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

                    if msg is latest_human and pending is not None:
                        user_input = pending["original_input"]
                        relevant_docs = pending["relevant_docs"] or None

                    # 仅从原始输入提取附件，避免将检索证据里的相同文字当成附件。
                    attachment_content = []
                    att_matches = re.findall(
                        r"用户上传附件内容 \d+：(.*?)(?=\n\n|$)",
                        user_input, re.DOTALL
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
        self._pending_rag_turn.pop(conversation_id, None)


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

