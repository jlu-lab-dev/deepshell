import json
import os
import urllib.parse
import webbrowser


def atomic_result(success, message, **kwargs):
    """
    一个更灵活的结果生成器。

    Args:
        success (bool): 操作是否成功。
        message (str): 操作结果的消息。
        **kwargs: 任意数量的关键字参数，将作为返回字典的核心数据。
                  例如: found_files=["path1", "path2"]

    Returns:
        dict: 一个包含执行状态和所有传入数据的字典。
    """
    result = {
        "success": success,
        "message": message
    }
    # 将所有传入的关键字参数合并到结果字典中
    result.update(kwargs)
    return result


def open_browser():
    """
    打开默认浏览器的首页。
    :return: dict 包含 success 与 message
    """
    try:
        webbrowser.open("about:blank")  # 打开空白页
        return {"success": True, "message": "浏览器已打开"}
    except Exception as e:
        return {"success": False, "message": f"打开浏览器失败: {e}"}


def search_in_browser(query, engine="bing"):
    """
    打开浏览器并搜索指定关键词。

    :param query: 要搜索的内容
    :param engine: 搜索引擎，可选值 "google"、"bing"、"baidu"（默认 google）
    :return: 操作结果提示信息
    """
    try:
        # URL encode
        encoded_query = urllib.parse.quote(query)

        # 根据搜索引擎选择 URL
        if engine.lower() == "google":
            url = f"https://www.google.com/search?q={encoded_query}"
        elif engine.lower() == "bing":
            url = f"https://www.bing.com/search?q={encoded_query}"
        elif engine.lower() == "baidu":
            url = f"https://www.baidu.com/s?wd={encoded_query}"
        else:
            return {"success": False, "message": f"不支持的搜索引擎: {engine}"}

        # 打开浏览器
        webbrowser.open(url)
        return {"success": True, "message": f"已在浏览器中打开 {engine} 搜索页面: {query}"}
    except Exception as e:
        return {"success": False, "message": f"搜索失败: {e}"}


# 工具映射表
FUNCTION_MAP = {
    "open_browser": open_browser,
    "search_in_browser": search_in_browser,
}



