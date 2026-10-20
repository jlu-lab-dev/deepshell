# DeepShell 评测

正式基准入口为 [benchmark_v1](benchmark_v1/README.md)，通用检索评测工具位于
[retrieval](retrieval/README.md)。正式实验总结见
[rag_baseline_v1.md](../docs/experiments/rag_baseline_v1.md)。

```text
evals/
├── benchmark_v1/     # 364 题数据、Gold 绑定、四方法对照与 Judge
│   ├── data/         # all / dev / eval / manifest；本地绑定产物被 Git 忽略
│   ├── results/      # 本地正式基线 dev_gold_v11，被 Git 忽略
│   └── tests/
└── retrieval/        # 通用检索、RRF、同页扩展与可选生成评测
    ├── package/      # 历史 RRF 接入说明与参考补丁
    └── tests/
```

题集统一放在 `benchmark_v1/data/`。检索工具默认读取该目录下的
`enterprise_bound.jsonl`，由 `enterprise_all.jsonl` 经 `bind_gold` 生成。

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests evals/retrieval/tests tests/test_rrf_integration.py tests/test_page_context.py -q
uv run --no-sync python -m evals.benchmark_v1.validate
```

源代码、原始题集、测试和实验总结纳入版本管理。运行结果、当前 Chroma UUID 绑定、
绑定报告和运行日志只保留本地。临时结果核验后可清理，正式基线保留完整逐题记录。
