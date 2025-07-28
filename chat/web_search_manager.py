import json
import requests
import uuid
from typing import Dict, List, Any, Optional
import logging
from utils.decorators import singleton
from config.config_manager import ConfigManager


@singleton
class WebSearchManager:
    """Web search manager that interfaces with MCP search service"""
    
    def __init__(self, is_enabled=True):
        self.config_manager = ConfigManager()
        self.mcp_url = "http://localhost:3000/mcp"
        self.session_id = None
        self.is_enabled = is_enabled
        
    def _initialize_session(self) -> bool:
        """Initialize MCP session"""
        try:
            init_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "DeepShell",
                        "version": "1.0"
                    }
                }
            }
            
            response = requests.post(
                self.mcp_url,
                json=init_request,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json, text/event-stream"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                if "mcp-session-id" in response.headers:
                    self.session_id = response.headers["mcp-session-id"]
                    logging.info(f"MCP session initialized: {self.session_id}")
                    return True
            
            logging.error(f"Failed to initialize MCP session: {response.status_code}")
            return False
            
        except Exception as e:
            logging.error(f"Error initializing MCP session: {e}")
            return False
    
    def _ensure_session(self) -> bool:
        """Ensure MCP session is active"""
        if not self.session_id:
            return self._initialize_session()
        return True
    
    def _parse_sse_response(self, response_text: str) -> dict:
        """Parse Server-Sent Events response format"""
        try:
            lines = response_text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data_part = line[6:]  # Remove 'data: ' prefix
                    return json.loads(data_part)
            return {}
        except Exception as e:
            logging.error(f"Error parsing SSE response: {e}")
            return {}
    
    def _fix_encoding(self, text: str) -> str:
        """Fix encoding issues with Chinese text"""
        if not text:
            return text
            
        try:
            # 尝试修复常见的UTF-8编码问题
            if any(ord(char) > 255 for char in text):
                return text  # 已经是正确的Unicode
            
            # 尝试修复编码
            fixed_text = text.encode('latin-1').decode('utf-8')
            return fixed_text
        except (UnicodeDecodeError, UnicodeEncodeError):
            # 如果修复失败，返回原文本
            return text

    def search_web(self, query: str, engine: str = "bing", max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web using MCP service
        
        Args:
            query: Search query
            engine: Search engine to use (bing, duckduckgo, baidu, etc.)
            max_results: Maximum number of results to return
            
        Returns:
            List of search results
        """
        logging.info(f"[WEBSEARCH执行] 开始搜索 | 查询: '{query}' | 引擎: {engine} | 启用状态: {self.is_enabled}")
        
        if not self.is_enabled:
            logging.warning(f"[WEBSEARCH执行] 网络搜索已禁用")
            return []
            
        try:
            if not self._ensure_session():
                return []
            
            search_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "query": query,
                        "engines": [engine],
                        "limit": max_results
                    }
                }
            }
            
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json, text/event-stream"
            }
            if self.session_id:
                headers["mcp-session-id"] = self.session_id
            
            response = requests.post(
                self.mcp_url,
                json=search_request,
                headers=headers,
                timeout=15
            )
            
            # 确保响应以UTF-8解码
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                # 解析 SSE 响应或 JSON 响应
                if response.headers.get("Content-Type", "").startswith("text/event-stream"):
                    result = self._parse_sse_response(response.text)
                else:
                    result = response.json()
                
                if "result" in result and "content" in result["result"]:
                    search_results = []
                    # 解析 MCP 返回的搜索结果
                    content = result["result"]["content"]
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                try:
                                    # 解析 JSON 格式的搜索结果
                                    text_content = item.get("text", "")
                                    parsed_data = json.loads(text_content)
                                    
                                    # 根据 MCP 服务的返回格式解析
                                    if isinstance(parsed_data, dict) and "results" in parsed_data:
                                        mcp_results = parsed_data["results"]
                                        for mcp_result in mcp_results:
                                            # 修复编码问题
                                            title = self._fix_encoding(mcp_result.get("title", "未知标题"))
                                            snippet = self._fix_encoding(mcp_result.get("description", ""))
                                            url = mcp_result.get("url", "")
                                            source = self._fix_encoding(mcp_result.get("source", ""))
                                            
                                            search_results.append({
                                                "title": title,
                                                "snippet": snippet,
                                                "url": url,
                                                "source": source,
                                                "engine": mcp_result.get("engine", engine)
                                            })
                                    else:
                                        # 兼容旧格式
                                        search_results.append({
                                            "title": "搜索结果",
                                            "snippet": self._fix_encoding(text_content),
                                            "url": "",
                                            "source": "",
                                            "engine": engine
                                        })
                                except json.JSONDecodeError:
                                    # 作为普通文本处理
                                    search_results.append({
                                        "title": "搜索结果", 
                                        "snippet": self._fix_encoding(item.get("text", "")),
                                        "url": "",
                                        "source": "",
                                        "engine": engine
                                    })
                    
                    logging.info(f"[WEBSEARCH执行] 搜索成功 | 获得结果: {len(search_results)} 条")
                    for i, result in enumerate(search_results[:3]):  # 只记录前3条
                        logging.info(f"[WEBSEARCH结果{i+1}] 标题: {result.get('title', '')[:50]}...")
                    return search_results[:max_results]
                    
            logging.error(f"[WEBSEARCH执行] 搜索失败 | HTTP状态码: {response.status_code}")
            return []
            
        except Exception as e:
            logging.error(f"[WEBSEARCH执行] 搜索异常 | 错误: {e}")
            return []
    
    def get_search_context(self, query: str, engine: str = "bing", max_results: int = 3) -> str:
        """
        Get search results formatted as context for AI model
        
        Args:
            query: Search query
            engine: Search engine to use
            max_results: Maximum number of results
            
        Returns:
            Formatted search results as string
        """
        logging.info(f"[WEBSEARCH格式化] 开始格式化搜索结果 | 查询: '{query}'")
        
        results = self.search_web(query, engine, max_results)
        
        if not results:
            logging.warning(f"[WEBSEARCH格式化] 未获得搜索结果")
            return "未找到相关的网络搜索结果。"
        
        context_pieces = []
        for i, result in enumerate(results):
            title = result.get("title", "未知标题")
            snippet = result.get("snippet", "")
            url = result.get("url", "")
            
            context_piece = f"[搜索结果 {i+1}] {title}\n{snippet}"
            if url:
                context_piece += f"\n来源: {url}"
            context_pieces.append(context_piece)
        
        formatted_context = "\n\n".join(context_pieces)
        logging.info(f"[WEBSEARCH格式化] 格式化完成 | 结果长度: {len(formatted_context)} 字符")
        
        return formatted_context
    
    def is_search_query(self, query: str) -> bool:
        """
        Determine if a query should trigger web search
        
        Args:
            query: User query
            
        Returns:
            True if query should trigger web search
        """
        # 简单的规则判断，可以后续优化
        search_indicators = [
            "搜索", "查找", "最新", "新闻", "当前", "现在", "今天", "最近",
            "什么是", "如何", "怎么", "为什么", "在哪里", "什么时候",
            "search", "find", "latest", "news", "current", "now", "today", "recent",
            "what is", "how to", "why", "where", "when"
        ]
        
        query_lower = query.lower()
        should_search = any(indicator in query_lower for indicator in search_indicators)
        
        logging.info(f"[WEBSEARCH检查] 查询: '{query}' | 是否触发搜索: {should_search}")
        
        return should_search
    
    def set_enabled(self, enabled: bool):
        """Enable or disable web search"""
        self.is_enabled = enabled
        
    def get_available_engines(self) -> List[str]:
        """Get list of available search engines"""
        return ["bing", "duckduckgo", "baidu", "csdn", "brave", "exa"] 