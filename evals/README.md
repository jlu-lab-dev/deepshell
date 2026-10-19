# DeepShell 中科方德手册 RAG 基线（v0.1）

本目录是两份官方 PDF 对应的**28 道起步测试题**，不代表原定 60 题的最终冻结评测集。

## 文件说明
- `rag_questions_starter.jsonl`：共 28 条，其中 20 条 dev，8 条 eval。24 条有答案、4 条跨知识库负例。
- `rag_questions_preview.csv`：方便 Excel 打开和人工逐条检查。
- 原始 PDF 由你本地保管，不应未经授权随公开项目提交整个手册。

## 知识库
- `KB_A_Desktop_V5` → PDF `zm_yhsc.pdf`，方德桌面操作系统 V5.0-G230，98 页。
- `KB_B_Server_V4` → PDF `方德高可信服务器操作系统V4.0-用户手册.pdf`，方德高可信服务器操作系统 V4.0，163 页。

## D1 使用步骤
1. 在 DeepShell 创建两个知识库，分别导入 PDF，一库一文档。
2. 保持当前 `config/rag.yaml`、Embedding 和模型设置不变，以免改变基线。
3. 检查文件是否导入成功、分块数是否大于 0、终端有无错误。
4. 在聊天页面一次只选择一库，按 JSONL 的 `knowledge_bases` 提问并记录答复。
5. 对跨库负例检查检索元数据；仅凭模型答出了被禁止的答案，不能断言发生检索泄漏。
6. 不要把这 28 条结果当作已完成严格的 Recall@5 或 MRR@10：`gold_chunk_ids` 目前为 null，须先读取实际 Chroma 文档 ID，结合手册页码确认每个问题的 relevant chunk。
7. 后续扩展到原计划 60 道，按 40 开发/20 冻结验收，并固定文档、索引、切分参数和评测方法。

## 标注口径
- `evidence.page` 是 PDF 阅读器显示的 1 起始页码，已按照原文件核查关键词。
- `reference_answer` 是参考事实，不要求生成答案完全逐字匹配。
- `evidence.search_terms` 仅用于人工定位，不是自动计算 Recall 的可靠标注。
- `task_type=cross_kb_unanswerable` 表示当前选库中不得引用**另一个手册的版本专有信息**。
- 暂时只做只读问答评测，不让 Agent 执行手册中出现的磁盘格式化、删除或系统级命令。

## 数据格式
`id, split, task_type, knowledge_bases, question, reference_answer, evidence, gold_chunk_ids, notes`。

## 开发说明
DeepShell 当前 `utils/document_loader.py` 使用 `PyPDFLoader` 直接解析 PDF，`config/rag.yaml` 含 `.pdf`，默认 `chunk_size=128`，`chunk_overlap=32`。本轮暂不改原始分块策略，记录原版效果后再对照。
