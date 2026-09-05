from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from backend.core.rag.vector_store import VectorstoreService
from backend.utils.prompt_handle import load_rag_prompt
from backend.models.model_factory import chat_model
from backend.utils.config_handle import rag_config


class RagService:
    def __init__(self):
        self.vector_store = VectorstoreService()
        self.prompt_txt = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_txt)
        self.model = chat_model
        self.chain = self._int_chain()

    def _int_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()   #以字符串的形式返回
        return chain

    # [DB改造] 原实现通过 Chroma retriever + filter 字典检索；
    # 新实现改为调用 pgvector 服务的语义检索方法：
    #   知识库   → search_knowledge（knowledge_chunks 表）
    #   对话记忆 → search_messages（message_embeddings 精筛层，命中即返回原文）
    # 不再需要 k_metadata_type / m_metadata_type 等 Chroma 元数据过滤。
    def retrieve_knowledge(self, query: str) -> List[Document]:
        return self.vector_store.search_knowledge(query)

    def retrieve_chat_memory(self, query: str, user_id: str, session_id: str) -> List[Document]:
        # [DB改造-修复] 原实现检索条件写 {"type": "memory"}，但写入端元数据实际是
        # rag_config["m_metadata_type"]="chat_history"，两者对不上导致记忆永远检索不到；
        # 新实现直接按 user_id/session_id SQL 条件过滤，不再有 type 错配问题。
        docs = self.vector_store.search_messages(query, user_id, session_id)
        # 按时间倒序排序（沿用原时序优化：优先保留较新内容）
        docs.sort(
            key=lambda d: d.metadata.get("msg_time", ""),
            reverse=True
        )
        return docs

    #将用户提问和资料注入chain
    def rag_summary(self, user_id: str, session_id: str, quest: str, use_knowledge: bool = True, use_memory: bool = True):
        docs = []
        if use_knowledge:
            docs.extend(self.retrieve_knowledge(quest))
        if use_memory:
            docs.extend(self.retrieve_chat_memory(quest, user_id, session_id))
        context = ""
        count = 0
        for doc in docs:
            count += 1
            context += f"参考资料{count}，参考内容为{doc.page_content},元数据为{doc.metadata}\n"
        return self.chain.invoke(
            {
                "input": quest,
                "context": context
            }
        )
    """ 考虑历史对话注入时机 """


rag_service = RagService()
