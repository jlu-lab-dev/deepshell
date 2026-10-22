# DeepShell RAG 检索基线 v1

基线标识：`dev_gold_v11`。实验日期：2026-10-20。原始结果保留于
`evals/benchmark_v1/results/dev_gold_v11/summary.json` 与 `details.jsonl`，本总结从该汇总提取。

## 范围与配置

完整题集共 364 题（dev 260 / eval 104）。本次只评测 dev / explicit 的 114 题，
其中 93 道可回答题全部成功绑定、21 道跨库负例，4 种方法合计 456 条记录。
未运行 LLM 生成或 Judge。

知识库为桌面 V5 的 `zm_yhsc.pdf` 与服务器 V4 用户手册；来源 SHA-256 见
`evals/benchmark_v1/data/manifest.json`。Gold 由当前本地 Chroma 索引重新绑定，
完整数据的绑定状态为 306 bound、3 既有 ID 验证通过、33 不适用、22 无来源锚点，缺失证据数为 0。

- Embedding：`BAAI/bge-small-zh-v1.5`。
- 分块大小 / 重叠：128 / 32。
- BM25 / Dense 每路候选：20 / 20；RRF 排名常数：60。
- 原始检索 K=3；同页扩展预算：1 页、新增最多 12 块、新增最多 2500 字符。
- 事实组之间为 AND，组内替代证据为 OR；Coverage 按每题的事实覆盖比例平均。

## 正式结果

事实指标的分母均为 93 道可回答题。

| 方法 | Fact Coverage | 全事实命中率 | Fact MRR | 平均上下文字符 | 检索 ms | 扩展 ms |
|---|---:|---:|---:|---:|---:|---:|
| hybrid | 76.34% | 75.27% | 0.6756 | 330.6 | 71.81 | 0.00 |
| rrf | 65.59% | 64.52% | 0.5771 | 336.8 | 62.58 | 0.00 |
| hybrid_page | 84.95% | 84.95% | 0.6858 | 1069.6 | 63.64 | 4.69 |
| rrf_page | 77.42% | 77.42% | 0.5913 | 1079.9 | 67.27 | 4.89 |

四种方法的知识库泄漏查询数均为 0，包括 21 道负例。
Hybrid+Page 的覆盖率比 Hybrid 高 8.61 个百分点；RRF+Page 比 RRF 高 11.83 个百分点。
本次 Hybrid 系列的事实覆盖率高于 RRF 系列；同页扩展同时增加了上下文长度。
耗时为单次运行均值，包含首次检索开销，不据此作稳定性能结论。

## Gold 修正与逐题核验

- `ENT-FAQ-0002`、`ENT-PARAP-0002` 拆为“安装方式”和“文件系统差异”两个事实组。
  两个基础方法的 Coverage 均为 0.5，两种同页扩展方法均为 1.0。
- `ENT-SHORT-0015`、`ENT-PARAP-0040` 增加第 78 页 `Super+D` 替代证据。
- `ENT-SHORT-0020`、`ENT-PARAP-0045` 增加第 78 页终端快捷键替代证据；原文错拼
  `Crtl+Alt+T` 已注明，标准答案保持 `Ctrl+Alt+T`。这 4 道快捷键题在四种方法下均命中。

修正前后标注口径不同，分数变化不能归为检索算法提升。

## 复现与产物管理

共享评测模块位于 `evals/retrieval`；RRF 实现、题集、测试与可选生成适配器均保留。
已清理旧开发包的接入说明、参考补丁及旧目录兼容代码。
默认不执行生成 API。

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests evals/retrieval/tests tests/test_rrf_integration.py tests/test_page_context.py -q
uv run --no-sync python -m evals.benchmark_v1.validate
uv run --no-sync python -m evals.benchmark_v1.bind_gold
uv run --no-sync python -m evals.benchmark_v1.evaluate --split dev --tier explicit --methods hybrid,rrf,hybrid_page,rrf_page --k 3 --output-dir evals/benchmark_v1/results/dev_gold_v11_repro
```

复现输出使用新目录，避免覆盖当前基线。原始题集、代码、测试和本总结纳入 Git；
绑定数据、绑定报告、原始运行结果和日志保留本地并忽略。
已清理旧 smoke / judge_smoke / llm_smoke / dev_explicit、早期检索输出、装配备份及运行日志。

## 结论边界与后续工作

本轮为检索开发基线，不能解释为模型答案准确率、忠实性或拒答率。
原题及其改写共享事实，逐问成绩不能视为独立样本显著性结论。
Silver 题仍待复核，独立 eval 集尚未作为本轮成绩使用。

后续先诊断快捷键正确页面是否进入候选，再决定采用查询改写、表格索引或精排；
固定上下文预算比较质量与成本，并以少量人工核验题补充生成和 Judge 实验。
