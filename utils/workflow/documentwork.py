# documentwork.py
import re
import json
import logging
from pathlib import Path
from typing import Dict, List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnableMap, RunnablePassthrough
from operator import itemgetter
from config.config_manager import ConfigManager
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai.embeddings import OpenAIEmbeddings
# 复用您已实现的DocumentProcessor
from utils.document_loader import DocumentProcessor  # 请替换实际导入路径

class DocumentWork:
    
    DOC_ANALYSIS_PROMPT = """基于以下文档内容和用户需求，生成分析结果：
    
    文档内容摘要：
    {document_summary}
    
    用户需求：{user_query}"""
    
    RAG_PROMPT = """结合以下文档片段和用户需求，生成详细分析：
    
    相关文档片段：
    {context}
    
    用户需求：{user_query}
    
    历史对话记录：{history}
    
    请用Markdown格式返回分析结果："""

    def __init__(self, config):
        self.llm = ChatOpenAI(
            model=config["model_name"],
            api_key=config["api_key"],
            base_url=config["api_base"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
        )
        self.embeddings = OpenAIEmbeddings(api_key=config["api_key"])
        self.document_processor = DocumentProcessor(chunk_size=10, chunk_overlap=2)

    def load_document(self, file_path):
        return self.document_processor.load_document(file_path)

    def create_vector_store(self, documents):
        """创建向量存储"""
        return FAISS.from_documents(documents, self.embeddings)

    def analyze_document(self, query, docs):
        """核心文档分析链"""
        if self._determine_analysis_type(query) == "summary":
            # 摘要生成链
            chain = (
                RunnablePassthrough()
                | PromptTemplate.from_template(self.DOC_ANALYSIS_PROMPT)
                | self.llm
                | StrOutputParser()
            )
        else:
            # 问答分析链
            chain = (
                RunnableMap({
                    "context": lambda x: x["context"],
                    "query": RunnablePassthrough(),
                    "history": RunnablePassthrough() 
                })
                | PromptTemplate.from_template(self.RAG_PROMPT)
                | self.llm
                | StrParserOutput()
            )
        
        return chain

    def _build_summary_chain(self):
        """构建摘要生成链"""
        return (
            RunnablePassthrough()
            | PromptTemplate.from_template(self.DOC_ANALYSIS_PROMPT)
            | self.llm
            | StrOutputParser()
        )

    def _build_qa_chain(self):
        """构建问答分析链""" 
        return (
            RunnableMap({
                "context": lambda x: x["context"],
                "query": RunnablePassthrough(),
                "history": RunnablePassthrough() 
            })
            | PromptTemplate.from_template(self.RAG_PROMPT)
            | self.llm
            | StrOutputParser()
        )

    def _determine_analysis_type(self, query):
        """判断分析类型"""
        if "总结" in query or "摘要" in query:
            return "summary"
        return "qa"

    def _generate_summary(self, docs):
        """生成文档摘要"""
        return "\n".join([d.page_content[:500] for d in docs[:3]])

    def _retrieve_context(self, query, docs):
        """检索相关文档片段"""
        vector_store = self.create_vector_store(docs)
        retriever = vector_store.as_retriever(k=3)
        return "\n\n".join([doc.page_content for doc in retriever.invoke(query)])

    def stream_analysis(self, query, docs):
        """流式处理入口"""
        chain = self.analyze_document(query, docs)
        print(f"核心文档分析链类型: {chain.__class__.__name__}")
        return chain.stream({
            "user_query": query,
            "document_summary": self._generate_summary(docs)
        })

# 使用示例
if __name__ == "__main__":
    config_manager = ConfigManager()
    # test get config
    config = config_manager.get_model_config('Qwen-PLUS')
    
    documentwork = DocumentWork(config)
    documents = documentwork.load_document("test.txt")
    
    # 流式输出
    for chunk in documentwork.stream_analysis("请总结本文核心观点", documents):
        print(chunk, end="")