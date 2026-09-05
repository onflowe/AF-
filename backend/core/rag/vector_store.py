# [DB改造] 原 vetot_store.py（基于 Chroma 的向量库）整体重写，Chroma 已弃用
# 向量统一落到 PostgreSQL(pgvector)，对应关系：
#   公共知识库（原 chroma collection）   → knowledge_chunks 表
#   消息精筛层（原"独立向量库"设计落位） → message_embeddings 表
#   摘要块粗筛层                          → summary_blocks.embedding 列
# 原 md5.txt 文件去重 → 改为 knowledge_chunks.source_md5 列 + UNIQUE 约束去重
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.utils.file_handle import load_txt, load_file_path, get_md5_has
from backend.utils.path_tool import get_abs_path
from backend.utils.config_handle import rag_config
from backend.utils.log_handle import logger
from backend.utils.pg_handle import get_conn
from backend.models.model_factory import embedding_model


class VectorstoreService:
    def __init__(self):
        # 知识库分块器（对话记忆/块摘要不再分块，直接整段嵌入）
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_config["chunk_size"],
            chunk_overlap=rag_config["chunk_overlap"],
            separators=rag_config["separators"],
            length_function=len
        )
        self.embedding_model = embedding_model

    # ------------------------------------------------------------------
    # 内部工具：文本嵌入（失败返回 None，不阻塞主流程）
    # ------------------------------------------------------------------
    def _embed(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        try:
            return self.embedding_model.embed_query(text)
        except Exception as e:
            logger.error(f"[DB改造] 文本嵌入失败（原文仍会入库，仅向量缺失）: {e}")
            return None

    # ==================================================================
    # 公共知识库（knowledge_chunks）
    # ==================================================================
    def load_document(self, data_path: str):
        """加载 data/ 下文档 → 分块 → 嵌入 → 写入 knowledge_chunks。
        [DB改造] 原实现：文件MD5写 md5.txt 去重后 add_documents 进 Chroma；
        新实现：以 knowledge_chunks.source_md5 查询去重（省去外部 md5 文件）。"""
        allowed_path = load_file_path(data_path, rag_config["allowed_type"])

        for path in allowed_path:
            md5_hex = get_md5_has(path)
            if not md5_hex:
                continue
            try:
                with get_conn() as conn:
                    # 按文件MD5去重：已加载过的文件跳过
                    row = conn.execute(
                        "SELECT 1 FROM knowledge_chunks WHERE source_md5 = %s LIMIT 1",
                        (md5_hex,),
                    ).fetchone()
                    if row:
                        logger.info(f"[文件加载]:{path}文件已被记录过")
                        continue

                    documents = load_txt(path)
                    if not documents:
                        logger.error(f"File empty: {path}")
                        continue
                    chunks = self.splitter.split_documents(documents)
                    if not chunks:
                        logger.error(f"File splitter empty: {path}")
                        continue

                    # 逐块嵌入并入库（同一事务，失败回滚不产生半截数据）
                    for idx, chunk in enumerate(chunks):
                        emb = self._embed(chunk.page_content)
                        if emb is None:
                            raise RuntimeError(f"嵌入失败，跳过文件: {path}")
                        conn.execute(
                            """INSERT INTO knowledge_chunks
                               (source_file, source_md5, chunk_index, content, embedding)
                               VALUES (%s, %s, %s, %s, %s)
                               ON CONFLICT (source_md5, chunk_index) DO NOTHING""",
                            (path, md5_hex, idx, chunk.page_content, emb),
                        )
                    conn.commit()
                logger.info(f"Document added success: {path}（{len(chunks)} 块）")
            except Exception as e:
                logger.error(f"File found false: {path},{str(e)}")

    def load_know(self):
        """知识库全量加载（入口与原实现一致）"""
        self.load_document(get_abs_path(rag_config["data_path"]))

    def search_knowledge(self, query: str, k: int = None) -> List[Document]:
        """公共知识库语义检索。返回 LangChain Document（与原检索器接口对齐）。"""
        k = k or rag_config["k"]
        emb = self._embed(query)
        if emb is None:
            return []
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT chunk_id, content, source_file,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM knowledge_chunks
                   ORDER BY embedding <=> %s::vector ASC
                   LIMIT %s""",
                (emb, emb, k),
            ).fetchall()
        docs = []
        for chunk_id, content, source_file, sim in rows:
            docs.append(Document(
                page_content=content,
                metadata={
                    "type": "knowledge",
                    "source_file": source_file,
                    "chunk_id": chunk_id,
                    "similarity": float(sim),
                },
            ))
        return docs

    # ==================================================================
    # 消息精筛层（message_embeddings）
    # ==================================================================
    def add_message_embedding(self, message_id: int, user_id: str, session_id: str,
                              block_id: Optional[str], role: str, content: str) -> bool:
        """为单条消息生成向量并写入精筛层。
        [DB改造] 原实现：窗口溢出后把 history 目录批量 add_documents 进 Chroma；
        新实现：消息落库时即逐条嵌入（增量、实时），不再需要批量同步。"""
        emb = self._embed(content)
        if emb is None:
            return False
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO message_embeddings
                       (message_id, user_id, session_id, block_id, role, content, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (message_id) DO NOTHING""",
                    (message_id, user_id, session_id, block_id, role, content, emb),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[DB改造] 消息向量写入失败 message_id={message_id}: {e}")
            return False

    def search_messages(self, query: str, user_id: str, session_id: str,
                        k: int = None) -> List[Document]:
        """对话记忆语义检索（精筛层）：命中即可拿到消息原文，无需回表。
        [DB改造] 原实现：Chroma 检索器 + filter 元数据（type/user_id/session_id）；
        新实现：pgvector 相似度查询 + SQL 条件过滤，天然支持混合检索。"""
        k = k or rag_config["k"]
        emb = self._embed(query)
        if emb is None:
            return []
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT message_id, role, content, created_at,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM message_embeddings
                   WHERE user_id = %s AND session_id = %s
                   ORDER BY embedding <=> %s::vector ASC
                   LIMIT %s""",
                (emb, user_id, session_id, emb, k),
            ).fetchall()
        docs = []
        for message_id, role, content, created_at, sim in rows:
            docs.append(Document(
                page_content=content,
                metadata={
                    "type": "memory",
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_id": message_id,
                    "role": role,
                    "msg_time": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "similarity": float(sim),
                },
            ))
        return docs

    # ==================================================================
    # 摘要块粗筛层（summary_blocks）—— 按设计文档建块，检索当前直接走精筛层，
    # 粗筛层为会话规模变大后的"先定位块再精筛"预留
    # ==================================================================
    def add_block(self, block_id: str, user_id: str, session_id: str,
                  block_summary: str, start_message_id: Optional[int],
                  end_message_id: Optional[int], message_count: int,
                  keywords: Optional[List[str]] = None) -> bool:
        """创建摘要块：对块摘要嵌入并写入 summary_blocks（嵌入失败时向量置 NULL 仍建块）。"""
        emb = self._embed(block_summary)
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO summary_blocks
                       (block_id, user_id, session_id, block_summary,
                        start_message_id, end_message_id, message_count, keywords, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (block_id, user_id, session_id, block_summary,
                     start_message_id, end_message_id, message_count,
                     keywords or [], emb),
                )
                conn.commit()
            if emb is None:
                logger.warning(f"[DB改造] 块 {block_id} 已建但无向量（嵌入失败）")
            return True
        except Exception as e:
            logger.error(f"[DB改造] 摘要块写入失败 block_id={block_id}: {e}")
            return False

    def search_blocks(self, query: str, user_id: str, session_id: str,
                      k: int = None) -> List[Document]:
        """粗筛层语义检索（预留接口：当前记忆检索直接走精筛层 search_messages）。"""
        k = k or rag_config["k"]
        emb = self._embed(query)
        if emb is None:
            return []
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT block_id, block_summary, start_message_id, end_message_id,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM summary_blocks
                   WHERE user_id = %s AND session_id = %s
                     AND embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector ASC
                   LIMIT %s""",
                (emb, user_id, session_id, emb, k),
            ).fetchall()
        return [Document(
            page_content=block_summary,
            metadata={
                "type": "block",
                "user_id": user_id,
                "session_id": session_id,
                "block_id": block_id,
                "start_message_id": start_message_id,
                "end_message_id": end_message_id,
                "similarity": float(sim),
            },
        ) for block_id, block_summary, start_message_id, end_message_id, sim in rows]


if __name__ == "__main__":
    vec = VectorstoreService()
    vec.load_know()
