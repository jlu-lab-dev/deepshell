# BGE Cross-Encoder 精排对照与技术选型

## 选型结论

保留 Hybrid + Page 作为当前已验证的检索方案基线。BGE Cross-Encoder 仅保留为可选实验模块，
本阶段结束对该配置的反复调参，下一阶段优先处理表格结构化检索。

在本次 CPU 对照中，Union + Reranker + Page 的事实覆盖率为 **82.80%**，
低于 Hybrid + Page 的 **84.95%**，下降 **2.15 个百分点**；P95 总耗时由 **90.38 ms**
增至 **3376.15 ms**。同页扩展组合的逐题比较为 **5 题改善、7 题退步、81 题不变**。
本次配置未显示足以支持接入应用默认流程的质量与延迟收益。

应用代码和配置保持原样，Reranker 未接入 GUI；导入精排模块和运行纯逻辑测试均不加载权重。
只有显式执行精排实验或调用模型精排函数时才加载模型。

## 实验范围与参数

- 结果标识：`rerank_dev`，原始汇总时间：2026-10-20T21:29:15（本地时间，Asia/Shanghai）。
- 复用 364 题完整基准及现有 Gold v1.1 绑定，不重新制作数据集或导入 PDF。
- 本次选择 dev / explicit 的 114 题：93 道有效 Gold 可回答题、21 道跨库负例。
- 5 种方法合计 570 条逐题记录；未调用 Qwen 或 Judge，独立 eval 集未参与调参。
- Embedding：`BAAI/bge-small-zh-v1.5`；分块大小 / 重叠：128 / 32。
- 精排模型：`BAAI/bge-reranker-base`，CPU，batch size=8，max length=512。
- BM25 与 Dense 各召回 Top-20，按真实 Chroma ID 去重后精排，最多 40 个候选，实际平均 36.114 个。
- 最终截取 Top-3，再可选同页扩展；扩展预算为 1 页、新增最多 12 块、新增最多 2500 字符。

事实组之间为 AND，组内替代证据为 OR。Fact Coverage 先计算每题覆盖的事实比例，再按题平均；
All-Facts 要求每题所有事实均命中；Fact MRR 按每个事实的首个有效证据排名计分。
Page 方法的下表指标按扩展后的完整上下文计算，原始 Top-3 指标单独保存在汇总的 `base_*` 字段中。

## 正式结果

事实指标的有效分母均为 93；耗时按每种方法全部 114 次查询统计。
P95 采用 nearest rank，包含检索、精排和扩展，不含模型加载、预热及答案生成。

| 方法 | Fact Coverage | All-Facts | Fact MRR | 平均总耗时 ms | P95 总耗时 ms |
|---|---:|---:|---:|---:|---:|
| BM25 | 77.42% | 76.34% | 0.6774 | 8.36 | 11.37 |
| Hybrid | 76.34% | 75.27% | 0.6864 | 64.45 | 84.47 |
| Hybrid + Page | 84.95% | 84.95% | 0.6966 | 72.14 | 90.38 |
| Union + Reranker | 77.42% | 77.42% | 0.6810 | 2310.35 | 3459.08 |
| Union + Reranker + Page | 82.80% | 82.80% | 0.6871 | 2296.28 | 3376.15 |

五种方法均通过知识库隔离检查，泄漏查询数为 0。
纯精排与 BM25 的事实覆盖率同为 77.42%，但精排显著增加了 CPU 延迟。

## 收益与退步分布

| 题型 | 有效题数 | Hybrid + Page | Union + Reranker + Page |
|---|---:|---:|---:|
| faq | 30 | 100.00% | 100.00% |
| hardware | 2 | 100.00% | 100.00% |
| shortcut | 17 | 58.82% | 76.47% |
| runlevel | 5 | 100.00% | 100.00% |
| paraphrase | 39 | 82.05% | 69.23% |

精排改善了部分窗口快捷键题，但工作区切换改写、运行级别改写题出现退步。
以下清单来自同一次正式实验的逐题配对，原始 Chunk ID 与事实排名保存在归档中：

| 变化 | 题号 | 问题 |
|---|---|---|
| 改善 | ENT-SHORT-0012 | 方德桌面 V5.0 执行“恢复窗口大小”操作的默认快捷键是什么？ |
| 改善 | ENT-SHORT-0013 | 方德桌面 V5.0 执行“改变窗口大小”操作的默认快捷键是什么？ |
| 改善 | ENT-SHORT-0017 | 方德桌面 V5.0 执行“最小化窗口”操作的默认快捷键是什么？ |
| 改善 | ENT-PARAP-0037 | 方德桌面 V5.0 执行“恢复窗口大小”操作的需要使用什么组合键？ |
| 改善 | ENT-PARAP-0038 | 方德桌面 V5.0 执行“改变窗口大小”操作的需要使用什么组合键？ |
| 退步 | ENT-PARAP-0026 | 方德桌面 V5.0 执行“切换到右侧工作区”操作的需要使用什么组合键？ |
| 退步 | ENT-PARAP-0027 | 方德桌面 V5.0 执行“切换到左侧工作区”操作的需要使用什么组合键？ |
| 退步 | ENT-PARAP-0049 | 方德服务器操作系统 V4.0 的运行级别 1 对应哪一种系统模式？ |
| 退步 | ENT-PARAP-0051 | 方德服务器操作系统 V4.0 的运行级别 3 对应哪一种系统模式？ |
| 退步 | ENT-PARAP-0052 | 方德服务器操作系统 V4.0 的运行级别 4 对应哪一种系统模式？ |
| 退步 | ENT-PARAP-0053 | 方德服务器操作系统 V4.0 的运行级别 5 对应哪一种系统模式？ |
| 退步 | ENT-PARAP-0054 | 方德服务器操作系统 V4.0 的运行级别 6 对应哪一种系统模式？ |

该结论限定当前模型、CPU 环境、小块切分与参数配置；未推断其他精排模型的表现。
本轮是单次开发集检索实验，原题与改写题相关，不能将指标解释为生成答案准确率或独立样本显著性结论。

## 保留、归档与清理

保留以下可复现代码及回归测试：

- [精排实现](../../rag/cross_encoder_reranker.py)
- [实验入口](../../evals/benchmark_v1/rerank_experiment.py)
- [精排回归测试](../../evals/benchmark_v1/tests/test_union_reranker.py)

本地保留 [正式汇总](../../evals/benchmark_v1/results/rerank_dev/summary.json)，
570 条逐题记录压缩归档为 [details.jsonl.gz](../../evals/benchmark_v1/results/rerank_dev/details.jsonl.gz)。
归档已通过逐字节还原校验；校验完成后移除未压缩副本及临时 `rerank_smoke/`。
`dev_gold_v11/`、正式题集、Gold 绑定数据和 Hybrid + Page 代码均保留。

运行结果目录被 Git 忽略，本选型文档适合纳入版本管理。模型权重是可重新下载的缓存，
可在确认未被其他项目共用后单独清理；Embedding 模型 `BAAI/bge-small-zh-v1.5` 必须保留。

本次清理已获用户确认：仅删除 `models--BAAI--bge-reranker-base` 缓存目录，
释放约 1.13 GB；Embedding 缓存保留。以后显式运行精排实验时需要重新下载权重。

完整性摘要（SHA-256）：

- `summary.json`：`f1df28163a1e981f2bc1a050cadeefda69eb975f60851380a0aeb1d38e7121f2`
- 原始 `details.jsonl` 内容：`161885454f9a8bf5ac0a46971500f6c1d89f6fe3ad985ab52331d52574ee7abd`
- `details.jsonl.gz`：`df7b3a03d898dac71afe5993c03ef7d7a64f4f2b830ab0bd4b937a09e49029fc`

读取归档无需模型：

```python
import gzip
import json

with gzip.open("evals/benchmark_v1/results/rerank_dev/details.jsonl.gz", "rt", encoding="utf-8") as f:
    records = [json.loads(line) for line in f if line.strip()]
```

## 按需复现

纯逻辑测试不需要权重：

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests/test_union_reranker.py -v
```

需要再次验证精排时才运行以下命令；缓存已清理时会重新下载模型，输出使用新目录以保留正式结果：

```powershell
uv run --no-sync python -m evals.benchmark_v1.rerank_experiment --split dev --tier explicit --methods bm25,hybrid,hybrid_page,union_rerank,union_rerank_page --k 3 --candidate-k 20 --output-dir evals/benchmark_v1/results/rerank_dev_repro
```

## 下一阶段

围绕 Top-20 诊断中两路候选并集仍缺 Gold 的 11 道题，优先研究快捷键表和运行级别表的结构化索引。
保留现有 Gold 与基线，用表格行级文本、来源页码及原文证据追溯检验召回变化；
将新增表格召回收益与同页扩展收益分别统计。本阶段不再以启用新技术为目标重复调整精排方案。
