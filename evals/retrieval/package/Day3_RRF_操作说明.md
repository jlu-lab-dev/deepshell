# 历史 RRF 接入参考

本目录保留早期 RRF 开发包中的参考补丁，现有实现和测试已迁移到 `evals/retrieval`。
补丁文件名中的 Day3 是历史名称。应用已接入 RRF，日常运行无需重新应用补丁或解压旧开发包。

- `rag/rrf_fusion.py`：按真实 Chroma ID 去重并融合两路排名。
- `evals/retrieval/retrieval_eval.py`：BM25、Dense、Hybrid、RRF 和事实指标。
- `evals/retrieval/pipeline_eval.py`：检索、同页扩展和可选生成适配器。
- `evals/benchmark_v1/data/`：正式题集与脚本生成的本地 Gold 绑定数据。
- `evals/retrieval/tests/test_rrf.py`：RRF 与多事实回归测试。
- `DeepShell_Day3_RRF_应用接入_参考.patch`：历史应用接入差异，供人工对照。

```powershell
uv run --no-sync python -m pytest evals/retrieval/tests tests/test_rrf_integration.py -q
```

GUI 使用 `config/rag.yaml` 中 `hybrid_search.fusion_strategy` 选择 `legacy` 或 `rrf`，
并读取 `rrf_k`。正式评测通过命令行指定方法，见 `evals/benchmark_v1/README.md`。
同组 Chunk ID 是 OR，不同事实组是 AND。正式结果见 `docs/experiments/rag_baseline_v1.md`。
