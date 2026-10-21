# DeepShell 通用检索评测

本模块提供正式 Benchmark 共用的检索、指标和生成适配接口，以及独立检索诊断入口。

- `retrieval_eval.py`：BM25、Dense、Hybrid、RRF 与应用检索接口的只读评测；按真实 Chunk ID 计算事实指标。
- `pipeline_eval.py`：正式基准使用的适配器，提供检索、同页扩展、完整证据、可选生成和模型加载接口。
- `tests/test_rrf.py`：RRF 排序、去重、来源隔离及 AND/OR 事实指标测试。
- `tests/test_retrieval_metrics.py`：检索指标和分母回归测试。

RRF 的应用实现位于 `rag/rrf_fusion.py`，同页扩展实现位于 `rag/page_context.py`。
独立精排模块位于 `rag/cross_encoder_reranker.py`，实验入口为
`evals.benchmark_v1.rerank_experiment`：将 BM25、Dense 各 Top-20 候选按 Chroma ID
合并去重，再由 BGE Cross-Encoder 选出 Top-K，可继续执行同页扩展。
当前作为独立实验使用，尚未接入 GUI 的默认检索流程。
本轮精排实验已结束，保留代码和正式结果供对照；该轮选型基线为 Hybrid + Page。
质量、CPU 延迟及逐题退步分析见
[精排技术选型报告](../../docs/experiments/reranker_comparison.md)。

GUI 现默认使用 **Hybrid + Table + Page**：`RAGManager.search()` 先合并原始 Hybrid
与表格命中并截取 Top-3，`Assistant` 再按 1 页 / 新增 12 块 / 新增 2500 字符扩展，
普通聊天、流式聊天和 Agent 首轮共用该流程，保留真实 Chunk ID、PDF 页码及引用编号。
表格路径当前仅支持 `table_facts.jsonl` 中已核对的 23 条快捷键和 7 条运行级别事实；
未匹配的查询继续使用 Hybrid，事实文件不可用时记录日志并回退 Hybrid。
配置见 `config/rag.yaml` 的 `hybrid_search.fusion_strategy: hybrid_table`；
`legacy` 和 `rrf` 仍可用于对照。修改配置后重启 GUI，Reranker 继续仅在显式实验时加载。

## 运行

从项目根目录执行，两个知识库 `KB_A_Desktop_V5`、`KB_B_Server_V4` 须已完成索引。
题集统一使用正式 Benchmark 数据，默认读取 `evals/benchmark_v1/data/enterprise_bound.jsonl`；
该文件由绑定脚本生成，也可以通过 `--dataset` 显式指定其他兼容数据。

```powershell
uv run --no-sync python -m pytest evals/retrieval/tests tests/test_rrf_integration.py -q
uv run --no-sync python -m evals.benchmark_v1.bind_gold
uv run --no-sync python -m evals.retrieval.retrieval_eval --split dev --methods bm25,dense,hybrid,rrf --k 3,5,10 --output-dir evals/retrieval/results/rrf_dev
```

结果写入被 Git 忽略的 `results/`。此入口按 split 读取全部质量层，适合候选召回诊断；
正式对照使用 `evals.benchmark_v1.evaluate --tier explicit`，以保留按质量层区分的统计口径。

## 指标和行为

事实组之间是 AND，组内 Chunk ID 是 OR。`fact_coverage` 为已覆盖事实比例，
`fact_all` 为所有事实是否均已覆盖，`fact_mrr` 为各事实倒数排名的平均。
页码命中只用于宽松定位；未标注 Gold 的问题不计入事实指标。

`hybrid` 调用 `hybrid_search()`；`rrf` 对相同规模的 BM25、Dense 候选按排名融合；
`app` 调用应用 `search()`，可能返回 `2*k` 个候选。
`pipeline_eval.run_one()` 仅在显式传入 LLM 时执行生成；默认不调用生成 API。

GUI 中的 `hybrid_search.fusion_strategy` 控制应用检索分支；直接评测指定方法无需修改配置。
跨库负例检查检索来源，拒答质量需要另行执行生成评测。
