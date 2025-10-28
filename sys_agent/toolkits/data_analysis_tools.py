import datetime
import json
import tempfile

from utils.llm_client import call_llm


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


MAX_RECORDS_FOR_LLM = 200

def generate_report_text(table_data: list, user_request: str):
    """
    调用大模型来分析数据并生成报告文本。
    """
    try:
        if table_data is None:
            # 返回一个对用户友好的错误信息
            return atomic_result(False, "错误：未能获取到上一步的表格数据，无法生成报告。")
        # 1. 数据预处理和安全检查
        data_to_process = table_data
        warning_message = ""
        if len(table_data) > MAX_RECORDS_FOR_LLM:
            warning_message = f"\n(注意: 原始数据包含 {len(table_data)} 行，为符合模型长度限制，仅分析了前 {MAX_RECORDS_FOR_LLM} 行。)"
            data_to_process = table_data[:MAX_RECORDS_FOR_LLM]

        data_json_string = json.dumps(data_to_process, ensure_ascii=False, indent=2)

        # 2. 在函数内部构建提示词 (Prompt)
        prompt = f"""
        【角色定义】
        你是一位专业、严谨的数据分析师。你的任务是分析所提供的销售数据，并根据用户的具体要求生成一份全面而简要的周报。

        【用户的要求】
        {user_request}

        【销售数据 (JSON格式)】
        {data_json_string}

        【任务要求】
        1.  **分析数据**: 仔细研究提供的JSON数据，识别关键趋势、模式、总计、平均值、最高点和最低点等相关信息。
        2.  **构建报告**: 输出必须是一份结构清晰的中文报告，包含标题、日期、摘要、详细分析和总结。
        3.  **输出格式**: 你的回答必须且只能是报告本身的文本，不包含任何额外的引言或结束语。

        请现在开始生成报告。
        """

        # 3. 调用可复用的LLM函数
        print("--- 正在调用AI进行数据分析... ---")
        # 这里会使用 call_llm 函数中默认的 "deepseek-chat" 模型
        report_content = call_llm(prompt)
        print("--- AI分析完成。---")

        # 4. 检查调用是否成功
        if report_content.startswith("错误："):
            # 如果调用失败，直接将错误信息返回
            return atomic_result(False, report_content)

        # 5. 封装成功的结果
        final_report = report_content + warning_message
        return atomic_result(True, "周报文本内容已通过 AI 成功生成。", report_text=final_report)

    except Exception as e:
        # 这个try-except块现在只捕获数据处理阶段的错误
        return atomic_result(False, f"在为AI准备数据时发生错误: {e}")


FUNCTION_MAP = {
    "generate_report_text": generate_report_text
}