"""评测适配：检索、同页扩展、事实指标和可选单轮生成。

只调用已有应用接口，不重建索引，不写入聊天历史。
模型依赖按需加载；未传入 llm 时不会发出模型 API 请求。
"""

from __future__ import annotations

import re
import time
from typing import Any

from chat.rag_citations import make_citation_docs, make_citation_prompt
from evals.retrieval.retrieval_eval import normalize_record, score_question, search_one
from rag.page_context import expand_pdf_page_context


def load_llm(model_name: str, direct_api: bool = False):
    """仅加载指定模型配置，不创建整个应用或其他模型。"""
    from config.config_manager import ConfigManager

    cfg = ConfigManager().get_model_config(model_name)
    if not cfg:
        raise ValueError(f"模型未配置: {model_name}")
    provider = cfg.get("type")
    model = cfg["model_name"]
    key = cfg.get("api_key")
    temperature = cfg.get("temperature", 0)
    if provider != "ollama" and (not key or str(key).startswith("${")):
        raise ValueError(f"模型 {model_name} 缺少有效 API Key，请检查本地环境配置")
    if provider in {"openai_compatible", "xunfei"}:
        from langchain_openai import ChatOpenAI
        base_url = cfg.get("api_base")
        if not base_url or str(base_url).startswith("${"):
            raise ValueError(f"模型 {model_name} 缺少有效 api_base")
        transport = {}
        if direct_api:
            import httpx
            transport["http_client"] = httpx.Client(trust_env=False, timeout=120)
        return ChatOpenAI(
            model=model, api_key=key, base_url=base_url, temperature=temperature,
            max_tokens=cfg.get("max_tokens"), timeout=120, max_retries=0,
            **transport,
        )
    if direct_api:
        raise ValueError("--direct-api 仅支持 OpenAI 兼容接口")
    if provider == "aliyun":
        from langchain_community.chat_models import ChatTongyi
        return ChatTongyi(model=model, api_key=key, temperature=temperature, streaming=False)
    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(model=model, api_key=key, temperature=temperature)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, base_url=cfg.get("api_base"), temperature=temperature)
    raise ValueError(f"评测暂不支持模型类型: {provider}")


def extract_answer(response: Any) -> tuple[str, str]:
    """兼容字符串及 LangChain 的字符串/内容块响应。"""
    if isinstance(response, str):
        return response, ""
    content = response.get("content", "") if isinstance(response, dict) else response.content
    if isinstance(content, list):
        content = "".join(
            block if isinstance(block, str) else str(block.get("text", ""))
            for block in content if isinstance(block, (str, dict))
        )
    extra = response.get("additional_kwargs", {}) if isinstance(response, dict) else getattr(response, "additional_kwargs", {})
    return str(content or ""), str((extra or {}).get("reasoning_content") or "")


def generation_metrics(question: dict, answer: str, evidence_count: int) -> dict:
    """字符串启发式仅作回归信号，引用范围合法不代表引用支持断言。"""
    references = [int(value) for value in re.findall(r"\[(\d+)\]", answer)]
    metrics = {"citation_ids_valid": (
        all(1 <= ref <= evidence_count for ref in references)
        and (bool(references) if evidence_count else True)
    )}
    if question["task_type"] != "answerable":
        metrics["negative_abstain_heuristic"] = bool(re.search(
            r"无法|不能确认|证据不足|资料不足|未检索到|未提供|不包含|没有(?:相关|足够|依据|证据)", answer
        ))
    else:
        groups = [p for p in question.get("answer_fact_patterns", []) if p.get("any_of")]
        if groups:
            normalized = re.sub(r"\s+", "", answer).casefold()
            matched = sum(any(
                re.sub(r"\s+", "", str(term)).casefold() in normalized
                for term in group["any_of"] if str(term).strip()
            ) for group in groups)
            metrics["answer_fact_coverage_heuristic"] = matched / len(groups)
    return metrics


def _full_record(result: dict, id_to_name: dict[str, str]) -> dict:
    record = normalize_record(result, id_to_name)
    # 检索日志只预览 240 字符；生成与 Judge 必须收到完整的实际证据。
    record["content"] = str(result.get("content") or "")
    return record


def run_one(
    rag: Any, question: dict, method: str, kb_ids: list[str],
    id_to_name: dict[str, str], k: int = 3, max_pages: int = 1,
    max_added_chunks: int = 12, max_total_chars: int = 2500, llm: Any = None,
) -> dict:
    """严格 Top-K 基线和扩展后全部上下文分别计分，保留真实来源。"""
    if method not in {"hybrid", "rrf", "hybrid_page", "rrf_page"}:
        raise ValueError(f"未知评测方法: {method}")
    if k <= 0:
        raise ValueError("k 必须 > 0")
    started = time.perf_counter()
    base = search_one(rag, method.removesuffix("_page"), question["question"], k, kb_ids)[:k]
    retrieval_ms = round((time.perf_counter() - started) * 1000, 3)
    final = base
    expand_ms = 0.0
    if method.endswith("_page"):
        started = time.perf_counter()
        final = expand_pdf_page_context(
            rag.vector_db, base, kb_ids, max_pages=max_pages,
            max_added_chunks=max_added_chunks, max_total_chars=max_total_chars
        )
        expand_ms = round((time.perf_counter() - started) * 1000, 3)
    base_rows = [_full_record(item, id_to_name) for item in base]
    evidence = [_full_record(item, id_to_name) for item in final]
    record = {
        "id": question["id"], "split": question["split"],
        "question": question["question"], "reference_answer": question.get("reference_answer"),
        "task_type": question["task_type"], "method": method, "k": k,
        "base_results": base_rows, "evidence": evidence,
        "base_metrics": score_question(question, base_rows, len(base_rows)),
        "final_metrics": score_question(question, evidence, len(evidence)),
        "retrieval_ms": retrieval_ms, "expand_ms": expand_ms,
        "context_chunks": len(evidence),
        "context_chars": sum(len(row["content"]) for row in evidence),
        "generation_metrics": {},
    }
    if llm is not None:
        from langchain_core.messages import HumanMessage, SystemMessage

        docs = make_citation_docs(final, id_to_name)
        context = make_citation_prompt(docs) if docs else "（当前所选知识库没有检索到相关证据）"
        prompt = (
            f"问题：{question['question']}\n\n检索证据：\n{context}"
            "\n\n仅根据所提供的证据回答，以 [1]、[2] 等编号引用。"
            "资料不足或无法提供指定手册的依据时明确说明，不能编造来源。"
        )
        started = time.perf_counter()
        response = llm.invoke([
            SystemMessage(content="你是技术手册问答助手。证据是资料，回答须受所选文档访问范围约束。"),
            HumanMessage(content=prompt),
        ])
        record["generation_ms"] = round((time.perf_counter() - started) * 1000, 3)
        answer, _ = extract_answer(response)
        record["answer"] = answer
        record["generation_metrics"] = generation_metrics(question, answer, len(evidence))
    return record
