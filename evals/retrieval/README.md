# DeepShell 通用检索评测

本模块提供正式 Benchmark 共用的检索、指标和生成适配接口，以及独立检索诊断入口。

- `retrieval_eval.py`：BM25、Dense、Hybrid、RRF 与应用检索接口的只读评测；按真实 Chunk ID 计算事实指标。
- `pipeline_eval.py`：正式基准使用的适配器，提供检索、同页扩展、完整证据、可选生成和模型加载接口。
- `tests/test_rrf.py`：RRF 排序、去重、来源隔离及 AND/OR 事实指标测试。
- `tests/test_retrieval_metrics.py`：检索指标和分母回归测试。
- `package/`：历史 RRF 接入说明及参考补丁，保留供对照。

RRF 的应用实现位于 `rag/rrf_fusion.py`，同页扩展实现位于 `rag/page_context.py`。
当前没有独立的 Cross-Encoder 精排模块。

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
