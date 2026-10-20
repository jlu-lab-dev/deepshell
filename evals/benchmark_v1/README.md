# DeepShell Enterprise RAG Benchmark v1

364 道两份方德手册相关题目：dev 260、eval 104；explicit 156、silver 179、legacy 29。
Explicit 表示来源直接支持，仍需区分人工核验范围；Silver 不混入正式 Gold 成绩。
当前正式开发集基线为 `results/dev_gold_v11/`，实验总结见
[rag_baseline_v1.md](../../docs/experiments/rag_baseline_v1.md)。

## 目录与依赖

- `data/enterprise_all.jsonl`：完整原始标注，修改 Gold 的入口。
- `data/enterprise_dev.jsonl`、`enterprise_eval.jsonl`：按 split 导出的副本，须与全集一致。
- `data/manifest.json`：题集统计与源 PDF 摘要。
- `bind_gold.py`：只读当前 Chroma，按 KB、文件、页码与原文绑定真实 Chunk ID。
- `evaluate.py`：Hybrid / RRF / Hybrid+Page / RRF+Page 对照。
- `judge.py`：可选生成质量评判；`validate.py` 和 `verify_pdf_sources.py` 用于数据校验。
- `tests/`：绑定、指标、适配器、生成和 Judge 的回归测试。
- `../retrieval/`：共享检索、RRF、同页扩展与生成评测工具，保留原有实现及测试。

`data/enterprise_bound.jsonl`、`data/binding_report.json`、`results/` 和临时运行日志
被 Git 忽略。本地绑定产物与当前索引 UUID 相关，重建索引后必须重新绑定。
正式结果本地保留，适合提交的指标与实验说明整理进 `docs/experiments/`。

## 校验和绑定

从项目根目录执行，先在 GUI 中为两个知识库完成索引：`KB_A_Desktop_V5`、`KB_B_Server_V4`。

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests evals/retrieval/tests -q
uv run --no-sync python -m evals.benchmark_v1.validate
uv run --no-sync python -m evals.benchmark_v1.bind_gold
```

只修改原始数据后重绑，不手工修改 `enterprise_bound.jsonl`。
`binding_report.json` 列出绑定状态；缺失锚点不能当作检索失败。

`evidence` 每个条目是一个必需事实（AND）；条目内 `alternatives` 是同一事实的备选证据（OR）：

```json
{
  "source": "zm_yhsc.pdf",
  "page": 35,
  "fact": "显示桌面的快捷键",
  "quote": "显示桌面 Super+D",
  "alternatives": [
    {"source": "zm_yhsc.pdf", "page": 78, "quote": "快捷键“Super+D”"}
  ]
}
```

页码按 PDF 阅读器的 1 起始页码填写。安装方式与文件系统差异分别建事实组。
终端第 78 页的 `Crtl+Alt+T` 按原文保留，错拼说明写入 `notes`，标准答案仍为 `Ctrl+Alt+T`。

## 正式检索对照

以下命令复现 114 道 explicit 开发题，输出到新目录，保留既有 `dev_gold_v11` 基线：

```powershell
uv run --no-sync python -m evals.benchmark_v1.evaluate --split dev --tier explicit --methods hybrid,rrf,hybrid_page,rrf_page --k 3 --output-dir evals/benchmark_v1/results/dev_gold_v11_repro
```

默认同页扩展预算为 1 页、新增最多 12 块、新增最多 2500 字符。
GUI 的预算独立配置；需要对齐时显式传入 `--max-pages`、`--max-added-chunks`、`--max-total-chars`。
每次运行写出 `details.jsonl` 和 `summary.json`，记录参数、指标分母、来源及耗时。
独立 eval 集只在实现冻结后验收，避免用于反复调参。

## 可选生成与 Judge

显式传入 `--llm-model` 才执行生成。先使用少量样本，输出到新的实验目录：

```powershell
uv run --no-sync python -m evals.benchmark_v1.evaluate --split dev --tier explicit --methods hybrid,hybrid_page --k 3 --limit 10 --llm-model Qwen-FLASH --output-dir evals/benchmark_v1/results/llm_trial
uv run --no-sync python -m evals.benchmark_v1.judge --details evals/benchmark_v1/results/llm_trial/details.jsonl --judge-model Qwen-FLASH --limit 20 --output-dir evals/benchmark_v1/results/judge_trial
```

代理连接重置时，OpenAI 兼容接口可用 `--direct-api` 在本次调用中忽略系统代理，仍校验 TLS。
模型配置和 API 费用需单独管理；生成与 Judge 指标需结合人工抽查解读。

## 指标

- `base_fact_coverage` / `final_fact_coverage`：原始 Top-K / 扩展上下文覆盖的事实比例，再按题平均。
- `base_all_facts` / `final_all_facts`：所有必需事实均命中的题目比例。
- `final_fact_mrr`：每题各事实倒数排名的平均，再按题平均。
- `kb_leak_queries`：返回未选择知识库内容的查询数。
- `verified_bound_questions` 和各指标的 `n`：有效分母；未绑定题不记为 0。
- `avg_context_chunks` / `avg_context_chars`、`avg_retrieval_ms` / `avg_expand_ms`：上下文成本与耗时。

未运行生成时，检索指标不能解释为答案准确率、忠实性或拒答率。
原题与改写题相关，不能将它们视作独立事实进行显著性推断。
