import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings, HuggingFaceBgeEmbeddings
from rank_bm25 import BM25Okapi
import jieba

from utils.document_loader import DocumentProcessor
from utils.decorators import singleton
from config.config_manager import ConfigManager
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


@singleton
class RAGManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_rag_config()
        self.vector_db = None
        self.embedding = None
        self.document_processor = DocumentProcessor(
            chunk_size=self.config['chunk_size'],
            chunk_overlap=self.config['chunk_overlap']
        )
        self._initialize_embedding()
        self._initialize_vector_db()

        self.self_rag_flag = self.config['self_rag']
        self.llm = None
        if self.self_rag_flag:
            self._initialize_llm()
            self._define_verification_prompts()

        # BM25 索引
        self._bm25_index: Optional[BM25Okapi] = None
        self._bm25_chroma_ids: List[str] = []
        self._bm25_content_map: Dict[str, Dict[str, Any]] = {}

    def _initialize_embedding(self):
        """Initialize the embedding model (API or local)."""
        # 优先读取新的 embedding key，兼容旧的 embeddings key
        cfg = self.config.get('embedding', self.config.get('embeddings', {}))
        emb_type = cfg.get('type', 'dashscope')

        if emb_type == 'local':
            local_cfg = cfg.get('local', {})
            model_path = os.path.expandvars(local_cfg.get('model_path', ''))
            model_name = local_cfg.get('model_name', 'BAAI/bge-small-zh-v1.5')
            device = local_cfg.get('device', 'cpu')
            encode_kwargs = local_cfg.get('encode_kwargs', {})

            # 优先用本地路径
            if model_path and os.path.exists(os.path.expanduser(model_path)):
                self.embedding = HuggingFaceBgeEmbeddings(
                    model_name=os.path.expanduser(model_path),
                    model_kwargs={"device": device},
                    encode_kwargs=encode_kwargs,
                )
                logging.info(f"[RAG] Local embedding loaded from: {model_path}")
            else:
                # fallback: 用 HF repo name 自动下载
                self.embedding = HuggingFaceBgeEmbeddings(
                    model_name=model_name,
                    model_kwargs={"device": device},
                    encode_kwargs=encode_kwargs,
                )
                logging.info(f"[RAG] Local embedding (auto-downloaded): {model_name}")
        else:
            self.embedding = DashScopeEmbeddings(
                model=cfg.get('model', 'text-embedding-v3'),
                dashscope_api_key=cfg.get('api_key'),
            )
            logging.info("[RAG] DashScope API embedding initialized")

    def _initialize_llm(self):
        """Initialize the LLM for Self-RAG."""
        try:
            self.llm = ChatOpenAI(
                api_key=self.config['feedback']['api_key'],
                model=self.config['feedback']['model_name'],
                temperature=self.config['feedback']['temperature'],
                base_url=self.config['feedback']["api_base"],
                max_tokens=self.config['feedback']["max_tokens"],
            )
        except Exception as e:
            print(f"Error initializing llm: {str(e)}")
            raise

    def _initialize_vector_db(self):
        """Initialize the vector database."""
        try:
            persist_directory = self.config['vector_db']['persist_directory']
            collection_name = self.config['vector_db']['collection_name']

            chromadb_dir = os.path.expanduser(persist_directory)
            if not os.path.exists(chromadb_dir):
                os.makedirs(chromadb_dir)

            self.vector_db = Chroma(
                persist_directory=chromadb_dir,
                embedding_function=self.embedding,
                collection_name=collection_name
            )
        except Exception as e:
            print(f"Error initializing vector database: {str(e)}")
            raise

        # 启动时重建 BM25 索引
        self._rebuild_bm25_index()

    # ── BM25 索引管理 ────────────────────────────────────────────────────────

    def _rebuild_bm25_index(self):
        """从 ChromaDB 拉取全部 chunk，重建 BM25 索引。"""
        try:
            result = self.vector_db._collection.get(
                include=["documents", "metadatas"]
            )
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            chroma_ids = result.get("ids", [])

            corpus = []
            self._bm25_chroma_ids = []
            self._bm25_content_map = {}

            for cid, doc_text, meta in zip(chroma_ids, docs, metas):
                tokenized = list(jieba.cut(doc_text))
                corpus.append(tokenized)
                self._bm25_chroma_ids.append(cid)
                self._bm25_content_map[cid] = {"text": doc_text, "metadata": meta}

            if not corpus:
                logging.info("[RAG] BM25 index skipped: no documents in database")
                self._bm25_index = None
                return

            self._bm25_index = BM25Okapi(corpus)
            logging.info(f"[RAG] BM25 index rebuilt: {len(corpus)} chunks")
        except Exception as e:
            logging.error(f"[RAG] BM25 index rebuild failed: {e}")
            self._bm25_index = None

    def _bm25_search(self, query: str, top_k: int = 20,
                     knowledge_bases: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """全局语料评分，先过滤允许的知识库，再选 Top-K。"""
        allowed = {str(kb) for kb in (
            knowledge_bases if knowledge_bases is not None else ["default"]
        )}
        if not allowed or top_k <= 0:
            return []
        if self._bm25_index is None:
            self._rebuild_bm25_index()
        if self._bm25_index is None:
            return []

        scores = self._bm25_index.get_scores(list(jieba.cut(query)))
        candidates = [
            i for i, cid in enumerate(self._bm25_chroma_ids)
            if str((self._bm25_content_map[cid]["metadata"] or {}).get(
                "knowledge_base", ""
            )) in allowed
        ]
        top_indices = sorted(
            candidates,
            key=lambda i: (-float(scores[i]), str(self._bm25_chroma_ids[i]))
        )[:top_k]

        results = []
        for idx in top_indices:
            # 注意：BM25 在小语料库下分数可能为负（如 N=1 时 IDF 为负），
            # 不再过滤，只按 top_k 取结果
            cid = self._bm25_chroma_ids[idx]
            info = self._bm25_content_map[cid]
            results.append({
                "chroma_id": cid,
                "content": info["text"],
                "metadata": info["metadata"],
                "bm25_score": float(scores[idx]),
            })
        for i, r in enumerate(results):
            source = (r["metadata"] or {}).get("source", "Unknown")
            logging.info(f"[RAG] BM25 #{i+1} score={r['bm25_score']:.4f} | source={source} | {r['content'][:30]}...")
        return results

    # ── 混合检索 ─────────────────────────────────────────────────────────────

    def hybrid_search(self, query: str, k: int = 5,
                      knowledge_bases: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """按真实 Chroma ID 融合已选知识库的 BM25 和语义结果。"""
        if k <= 0:
            return []
        cfg = self.config.get('hybrid_search', {})
        kw_weight = cfg.get('keyword_weight', 0.3)
        sem_weight = cfg.get('semantic_weight', 0.7)
        kw_top = cfg.get('keyword_top_k', 20)
        sem_top = cfg.get('semantic_top_k', 20)

        # ── Step 1: BM25 ──────────────────────────────────────────────────
        bm25_results = self._bm25_search(
            query, top_k=kw_top, knowledge_bases=knowledge_bases
        )
        bm25_by_id = {r["chroma_id"]: r for r in bm25_results}

        # ── Step 2: Semantic ──────────────────────────────────────────────
        sem_results = self._semantic_search(
            query, k=sem_top, knowledge_bases=knowledge_bases
        )
        sem_by_id = {r["chroma_id"]: r for r in sem_results}

        # ── Step 3: 加权融合（直接用原始分数，不归一化）──────────────
        # BM25 分数：越高越好，但小语料下可能为负数
        # 本轮保持原有原始数值加权策略；Chroma 返回的是距离。
        # 融合 = kw_weight * bm25_score + sem_weight * semantic_score
        # 阈值过滤：融合分 < score_threshold 的丢弃
        score_threshold = cfg.get('score_threshold', 0.3)
        fused = []
        for cid in bm25_by_id.keys() | sem_by_id.keys():
            bm25_result = bm25_by_id.get(cid, {})
            sem_result = sem_by_id.get(cid, {})
            bm25_s = bm25_result.get("bm25_score", 0.0)
            sem_s = sem_result.get("score", 0.0)
            fused_score = kw_weight * bm25_s + sem_weight * sem_s
            record = sem_result or bm25_result
            fused.append({
                "chroma_id": cid,
                "content": record["content"],
                "metadata": record["metadata"],
                "score": fused_score,
                "bm25_score": bm25_s,
                "semantic_score": sem_s,
                "distance": sem_result.get("distance"),
            })

        fused.sort(key=lambda x: (-x["score"], str(x["chroma_id"])))

        # 阈值过滤：融合分数低于阈值的丢弃
        score_threshold = cfg.get('score_threshold', 0.3)
        filtered = [r for r in fused if r["score"] >= score_threshold]

        logging.info(f"[RAG] Hybrid fusion: {len(fused)} candidates → {len(filtered)} after threshold={score_threshold}")
        for i, r in enumerate(filtered[:k]):
            source = (r["metadata"] or {}).get("source", "Unknown")
            logging.info(
                f"[RAG] Fusion #{i+1} fused={r['score']:.4f} "
                f"(bm25={r['bm25_score']:.4f}, sem={r['semantic_score']:.4f}) "
                f"| source={source} | {r['content'][:30]}..."
            )
        return filtered[:k]

    # ── 公开检索接口 ─────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 3,
               knowledge_bases: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """搜索并优化结果（如果启用 Self-RAG）。"""
        if k <= 0:
            return []
        cfg = self.config.get('hybrid_search', {})
        if cfg.get('enabled', False):
            if cfg.get("fusion_strategy", "legacy") == "rrf":
                from rag.rrf_fusion import rrf_fuse

                allowed = [str(kb) for kb in (
                    knowledge_bases if knowledge_bases is not None else ["default"]
                )]
                if not allowed:
                    return []
                bm25_results = self._bm25_search(
                    query, top_k=cfg.get("keyword_top_k", 20), knowledge_bases=allowed
                )
                dense_results = self.base_search(
                    query, k=cfg.get("semantic_top_k", 20), knowledge_bases=allowed
                )
                results = rrf_fuse(
                    [bm25_results, dense_results], top_k=k * 2,
                    rank_constant=cfg.get("rrf_k", 60)
                )
                if self.self_rag_flag:
                    results = self._optimize_results(query, results, k)
                return results

            results = self.hybrid_search(query, k=k * 2, knowledge_bases=knowledge_bases)
            # Self-RAG 优化后取 top k
            if self.self_rag_flag:
                results = self._optimize_results(query, results, k)
            return results
        else:
            raw = self.base_search(query, k=k, knowledge_bases=knowledge_bases)
            return [{**r, "bm25_score": 0} for r in raw]

    def _semantic_search(self, query: str, k: int = 3,
                         knowledge_bases: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """从 Chroma 原始结果取真实记录 ID，兼容没有 chunk_id 的旧索引。"""
        allowed = {str(kb) for kb in (
            knowledge_bases if knowledge_bases is not None else ["default"]
        )}
        if not allowed or k <= 0:
            return []
        try:
            where_filter = {"knowledge_base": {"$in": sorted(allowed)}}
            collection = self.vector_db._collection
            selected_ids = collection.get(where=where_filter, include=[])["ids"]
            if not selected_ids:
                return []
            results = collection.query(
                query_embeddings=[self.embedding.embed_query(query)],
                n_results=min(k, len(selected_ids)),
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            formatted = []
            for cid, text, meta, distance in zip(
                results["ids"][0], results["documents"][0],
                results["metadatas"][0], results["distances"][0]
            ):
                if str((meta or {}).get("knowledge_base", "")) not in allowed:
                    continue
                formatted.append({
                    "chroma_id": cid,
                    "content": text,
                    "metadata": meta or {},
                    "score": float(distance),
                    "distance": float(distance)
                })
            return formatted
        except Exception:
            logging.exception("[RAG] 语义检索失败")
            return []

    def base_search(self, query: str, k: int = 3,
                    knowledge_bases: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """纯语义检索，保留 Chroma 真实 ID、元数据和原始距离。"""
        return self._semantic_search(query, k=k, knowledge_bases=knowledge_bases)

    def get_relevant_context(self, query: str, k: int = 3,
                             knowledge_bases: Optional[List[str]] = None) -> str:
        """获取相关上下文（拼接字符串，用于 prompts）。"""
        results = self.search(query, k, knowledge_bases)
        if not results:
            return "No relevant information found."
        pieces = []
        for i, result in enumerate(results):
            source = result.get('metadata', {}).get('source', 'Unknown')
            pieces.append(f"[Document {i+1}] (Source: {source})\n{result['content']}\n")
        return "\n\n".join(pieces)

    # ── 文档管理 ─────────────────────────────────────────────────────────────

    def add_document(self, file_path: str, doc_id: str,
                     knowledge_base: str = "default") -> bool:
        """处理并添加文档到向量数据库。"""
        try:
            if not self.document_processor.is_supported_file_type(
                file_path, self.config["supported_file_types"]
            ):
                raise ValueError(f"不支持的文件类型: {Path(file_path).suffix}")

            logging.info("[RAG] 开始解析文档: %s", file_path)
            documents = self.document_processor.load_document(file_path)
            chunks = self.document_processor.chunk_documents(documents)
            if not chunks:
                raise ValueError("文档解析后没有有效文本分块")

            ids = []
            for index, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL, f"{knowledge_base}:{doc_id}:{index}"
                ))
                chunk.metadata["knowledge_base"] = str(knowledge_base)
                chunk.metadata["doc_id"] = str(doc_id)
                chunk.metadata["chunk_id"] = chunk_id
                chunk.metadata["chunk_index"] = index
                ids.append(chunk_id)

            logging.info("[RAG] 分块完成: %d chunks", len(chunks))
            # 保留已经验证过的原版批量写入方式。
            self.vector_db.add_documents(chunks, ids=ids)
            records = self.vector_db._collection.get(
                where={"doc_id": {"$eq": str(doc_id)}},
                include=[]
            )
            actual_count = len(records["ids"])
            if actual_count != len(chunks):
                raise RuntimeError(
                    f"Chroma 写入数量错误：预期 {len(chunks)}，实际 {actual_count}"
                )

            logging.info(
                "[RAG] 向量写入成功: doc_id=%s, chunks=%d",
                doc_id, actual_count
            )
            self._rebuild_bm25_index()
            return True
        except Exception:
            logging.exception("[RAG] 文档索引失败: %s", file_path)
            return False

    def delete_document(self, doc_id: str) -> bool:
        """从向量数据库删除文档（按 doc_id 过滤）。"""
        try:
            where_filter = {"doc_id": {"$eq": doc_id}}
            self.vector_db.delete(where=where_filter)
            # 重建 BM25 索引
            self._rebuild_bm25_index()
            return True
        except Exception as e:
            print(f"Error deleting document: {str(e)}")
            return False

    def clear_database(self) -> bool:
        """清空向量数据库。"""
        try:
            self.vector_db.delete_collection()
            self._initialize_vector_db()
            return True
        except Exception as e:
            print(f"Error clearing database: {str(e)}")
            return False

    def get_chunk_count(self, knowledge_base: Optional[str] = None) -> int:
        """获取 chunk 总数。"""
        try:
            if knowledge_base:
                results = self.vector_db._collection.get(
                    include=[],
                    where={"knowledge_base": knowledge_base}
                )
                return len(results['ids'])
            else:
                return self.vector_db._collection.count()
        except Exception as e:
            print(f"Error getting document count: {str(e)}")
            return 0

    def get_collection_name(self) -> str:
        """获取当前 collection 名称。"""
        return self.config['vector_db']['collection_name']

    # ── Self-RAG ─────────────────────────────────────────────────────────────

    def _define_verification_prompts(self):
        self.relevance_verification_prompt = PromptTemplate(
            input_variables=["query", "document_content"],
            template="""请判断以下文档内容是否与问题相关且信息准确。相关且准确回答Y，否则N。
            问题：{query}
            文档内容：{document_content}
            回答（Y/N）："""
        )

    def _optimize_results(self, query: str, raw_results: List[Dict], final_k: int) -> List[Dict]:
        """使用 Self-RAG 机制优化搜索结果。"""
        verified = []
        for result in raw_results:
            if self._verify_relevance(query, result['content']):
                print(f"验证通过: {result['content']}")
                verified.append(result)
            else:
                print(f"验证不通过: {result['content']}")
            if len(verified) >= final_k:
                break

        if len(verified) < final_k:
            verified += [r for r in raw_results if r not in verified][:final_k - len(verified)]

        return sorted(verified[:final_k], key=lambda x: x.get('score', 0), reverse=True)

    def _verify_relevance(self, query: str, content: str) -> bool:
        chain = self.relevance_verification_prompt | self.llm
        try:
            response = chain.invoke({
                "query": query,
                "document_content": content
            }).content.strip().upper()
            return "Y" in response
        except Exception as e:
            print(f"验证失败: {str(e)}")
            return False


if __name__ == "__main__":
    rag_manager = RAGManager()
    rag_manager.clear_database()
    rag_manager.add_document("test.txt", knowledge_base="kb1")
    print(f"kb1检索: {rag_manager.get_relevant_context('吉林大学', k=3, knowledge_bases=['kb1'])}")
    print(f"kb2检索（应为空）: {rag_manager.get_relevant_context('吉林大学', k=3, knowledge_bases=['kb2'])}")
