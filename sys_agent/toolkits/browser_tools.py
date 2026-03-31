# sys_agent/toolkits/browser_tools.py
"""
浏览器工具集。
提供浏览器启动和关键词搜索功能。
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any

from ._base import ok, fail, require_non_empty

_ENGINES = {"google": "https://www.google.com/search?q=",
            "bing":   "https://www.bing.com/search?q=",
            "baidu":  "https://www.baidu.com/s?wd="}


def open_browser() -> dict[str, Any]:
    """打开系统默认浏览器空白页。"""
    try:
        webbrowser.open("about:blank")
        return ok("浏览器已打开")
    except Exception as e:
        return fail(f"打开浏览器失败: {e}")


def search_in_browser(query: str, engine: str = "bing") -> dict[str, Any]:
    """使用指定搜索引擎搜索关键词。"""
    try:
        require_non_empty(query, "query")
        engine_key = engine.lower()
        if engine_key not in _ENGINES:
            return fail(f"不支持的搜索引擎，请使用 google / bing / baidu，当前: {engine}")
        url = _ENGINES[engine_key] + urllib.parse.quote(query)
        webbrowser.open(url)
        return ok(f"已在 {engine} 搜索: {query}", search_url=url)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except Exception as e:
        return fail(f"搜索失败: {e}")


FUNCTION_MAP: dict[str, callable] = {
    "open_browser": open_browser,
    "search_in_browser": search_in_browser,
}
