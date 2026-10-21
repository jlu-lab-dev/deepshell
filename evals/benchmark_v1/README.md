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

## Qwen 端到端方案对照

`answer_experiment.py` 对比冻结的 Hybrid+Page 和 Hybrid+Table+Page，复用真实
Chroma Chunk、表格旁路和同页扩展。固定 Top-3、1 页 / 新增 12 块 / 新增 2500 字符，
不修改数据、索引或 GUI。两方法按题交替运行，使用相同生成提示及参数。
默认 Qwen-FLASH 生成、Qwen-PLUS 独立调用评分，温度均为 0。
生成端 Qwen3 默认显式关闭思考模式；需要时使用 `--enable-thinking`，该设置也参与续跑校验。
思考开关遵循[阿里云官方 API 说明](https://www.alibabacloud.com/help/zh/model-studio/deep-thinking)，
只作用于本实验，不修改 GUI 模型配置。空回答或被截断的输出记为调用失败并保存结束原因与 token 数，不能直接参与评分。
生成模型只看到问题和实际上下文；参考答案、Gold 事实与 OR 备选原文只交给评委。

先检查分母和配置，此命令不连接 Chroma 或模型，也不创建结果目录：

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests/test_answer_experiment.py -q
uv run --no-sync python -m evals.benchmark_v1.answer_experiment --dry-run
```

真实调用会产生生成和评分 API 费用。先用 Dev 小样本检查链路，再运行 42 道
Explicit Eval（34 道 Gold、8 道真实负例；84 次生成、最多 84 次质量评分及 68 次引用核验）：

```powershell
uv run --no-sync python -m evals.benchmark_v1.answer_experiment --split dev --tier explicit --ids ENT-FAQ-0002,ENT-SHORT-0001,ENT-RUNLE-0002,ENT-CROSS-0001 --output-dir evals/benchmark_v1/results/answer_smoke
uv run --no-sync python -m evals.benchmark_v1.answer_experiment --split eval --tier explicit --output-dir evals/benchmark_v1/results/answer_eval_explicit
```

可用 `--llm-model` / `--judge-model` 指定已有模型配置；`--max-tokens` 和
`--judge-max-tokens` 默认均为 2048。`--direct-api` 仅对本次模型连接忽略环境代理，
保留 TLS 验证。运行生成模型和评委模型可属于同一厂商，因此仍有评委偏差。

输出 `manifest.json`、`details.jsonl`、`summary.json`、`summary.md`。保存实际完整证据、
生成提示、答案、评委原文、事实/引用逐项判定、token usage 和各阶段耗时。
质量评分与引用核验分开调用；引用核验仅看问题、实际证据和答案，不提供参考答案或 Gold，
防止将“非必需但正确的补充说明”误判为错误引用。
正确率和事实完整性只统计有效 Gold；拒答率只统计真实负例；未绑定题不混入负例。
引用编号合法率单独计算，不能代替语义引用支持。引用准确性是逐答案的引用支持比例宏平均，
Gold 答案未引用时计 0。评委看到的方法名被隐藏，但同源模型偏差仍需人工抽查。
逐题端到端延迟包含检索、扩展、生成，不包含离线评分及初始化耗时。

每条完成后保存进度；模型/评分失败立即停下并保留错误，失败不当作 0 分。
续跑使用原命令加 `--resume`；已生成答案可直接重试评委，避免重复生成。
数据、代码、模型参数、知识库映射及索引指纹不一致时拒绝续跑；已有结果禁止直接覆盖。
保留首次独立 Eval 的结果，不根据其错题修改 Gold、表格事实或检索参数。
本轮端到端结果、评分校准和待复核问题见
[answer_comparison.md](../../docs/experiments/answer_comparison.md)。
两道分区题的 PDF 原文核对及局部辅助复核结果见
[answer_manual_review.md](../../docs/experiments/answer_manual_review.md)，原始自动评分保留。

## 指标

- `base_fact_coverage` / `final_fact_coverage`：原始 Top-K / 扩展上下文覆盖的事实比例，再按题平均。
- `base_all_facts` / `final_all_facts`：所有必需事实均命中的题目比例。
- `final_fact_mrr`：每题各事实倒数排名的平均，再按题平均。
- `kb_leak_queries`：返回未选择知识库内容的查询数。
- `verified_bound_questions` 和各指标的 `n`：有效分母；未绑定题不记为 0。
- `avg_context_chunks` / `avg_context_chars`、`avg_retrieval_ms` / `avg_expand_ms`：上下文成本与耗时。

未运行生成时，检索指标不能解释为答案准确率、忠实性或拒答率。
原题与改写题相关，不能将它们视作独立事实进行显著性推断。
