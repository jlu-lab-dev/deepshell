# sys_agent/toolkits/data_analysis_tools.py
"""
数据分析工具集。
提供基于结构化数据的 AI 报告生成功能。
"""

from __future__ import annotations

import json
from typing import Any

from utils.llm_client import call_llm

from ._base import ok, fail

MAX_RECORDS_FOR_LLM = 200


def generate_report_text(
    table_data: list[dict[str, Any]], user_request: str,
) -> dict[str, Any]:
    """调用 LLM 分析表格数据并生成结构化报告文本。"""
    try:
        if not isinstance(table_data, list):
            return fail("table_data 必须是数组类型")

        # 截断超长数据
        warning = ""
        if len(table_data) > MAX_RECORDS_FOR_LLM:
            warning = (
                f"\n（注意：原始数据 {len(table_data)} 行，"
                f"已截取前 {MAX_RECORDS_FOR_LLM} 行进行分析。）"
            )
            table_data = table_data[:MAX_RECORDS_FOR_LLM]

        data_str = json.dumps(table_data, ensure_ascii=False, indent=2)
        prompt = f"""【角色定义】
你是一位专业、严谨的数据分析师。请根据以下销售数据，按照用户要求生成周报。

【用户的要求】
{user_request}

【销售数据 (JSON格式)】
{data_str}

【任务要求】
1. 分析数据，识别关键趋势、模式、合计、平均值等。
2. 输出结构清晰的中文报告，包含标题、日期、摘要、详细分析和总结。
3. 输出内容必须且只能是报告文本本身，不包含任何额外引言或结语。"""

        report = call_llm(prompt)
        if report.startswith("错误："):
            return fail(report)

        final = report + warning
        return ok("报告文本已生成", report_text=final)
    except Exception as e:
        return fail(f"生成报告时出错: {e}")


FUNCTION_MAP: dict[str, callable] = {
    "generate_report_text": generate_report_text,
}
