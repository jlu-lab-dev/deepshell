import os
import openai
from openai import OpenAI


def call_llm(prompt: str, model: str = "deepseek-chat") -> str:
    """
    一个可复用的、同步的函数，用于调用大语言模型并获取结果。

    Args:
        prompt (str): 发送给模型的完整、已格式化的提示词。
        model (str, optional): 要使用的模型名称。默认为 "deepseek-chat"。
                               请根据DeepSeek官方文档确认最新的模型标识符。

    Returns:
        str: 成功时返回模型的文本响应，失败时返回以"错误："开头的详细错误信息。
    """
    # 1. 从环境变量中安全地获取 API Key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "错误：未能获取 DEEPSEEK_API_KEY。请检查环境变量是否已设置。"

    # 2. 初始化 API 客户端
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )

        # 3. 发起 API 请求
        chat_completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            stream=False  # 工具函数需要等待完整结果，所以不使用流式输出
        )

        response_text = chat_completion.choices[0].message.content
        return response_text.strip()

    # 4. 精细化的错误处理
    except openai.APIConnectionError as e:
        return f"错误：无法连接到 DeepSeek API。请检查网络连接。详情: {e}"
    except openai.RateLimitError as e:
        return f"错误：已超出API速率限制。请稍后再试。详情: {e}"
    except openai.APIStatusError as e:
        return f"错误：API 返回了错误状态。状态码: {e.status_code}, 响应: {e.response}"
    except Exception as e:
        return f"错误：调用AI时发生未知错误。详情: {e}"