# [DB改造] 原 ShotMemory（JSON 文件版短期记忆）整体重写为 PgMemory（PostgreSQL 版）
# 原实现：history/{uid}/{sid}.json 存窗口消息 + history_re/{sid}_layerN.json/txt 存三层摘要，
#         超过18条时把整个 history 目录批量灌进 Chroma（md5.txt 去重），再裁剪 JSON 文件。
# 新实现（对应数据库重建文档）：
#   1. messages 表：消息全量持久化、永不删除（"取数层"，权威原文）；
#      滑动窗口只是 SQL 取最近 window_k*2 条，不再裁剪文件；
#   2. message_embeddings 表（精筛层）：消息落库时逐条嵌入，实时可检索，
#      不再有 18 条阈值/批量同步/Chroma 逻辑；
#   3. summary_blocks 表（粗筛层）：每 block_rounds 轮压缩生成一个摘要块并回填消息的 block_id；
#   4. summaries 表：三层摘要（1→2→3 每满 merge_threshold 条合并），
#      替代 history_re 下的 layer 文件；
#   5. users/sessions 表：首次消息时自动创建（当前前端固定 u001/s001，无注册流程）。
import json
import uuid
from typing import List, Optional, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from backend.utils.config_handle import rag_config
from backend.utils.log_handle import logger
from backend.utils.pg_handle import get_conn
from backend.utils.prompt_handle import load_memory_sum_prompt
from backend.models.model_factory import chat_model
from backend.core.rag.vector_store import VectorstoreService
from backend.core.rag.interfaces import IMemoryService


class PgMemory(IMemoryService):
    """基于 PostgreSQL 的记忆服务（短期窗口 + 摘要块 + 三层摘要 + 消息向量）"""

    def __init__(self):
        self.window_k = rag_config["window_k"]                # 短期记忆滑动窗口（轮）
        self.block_rounds = rag_config["block_rounds"]        # 每 n 轮生成一个摘要块
        self.merge_threshold = rag_config["summary_merge_threshold"]  # 摘要合并阈值（3）
        self.vector_store = VectorstoreService()
        self.summary_llm = chat_model                         # 摘要生成 LLM
        self.prompt_dict = json.loads(load_memory_sum_prompt())

    # ==================================================================
    # 核心接口实现（与原 ShotMemory 对外签名一致）
    # ==================================================================

    def add_message(self, user_id: str, session_id: str, user_input: str, ai_output: str) -> None:
        """写入一轮对话（user + assistant 两条）。[DB改造] 原实现写 JSON 文件，现写 messages 表"""
        self._ensure_user_session(user_id, session_id)

        # 1. 消息原文落库（messages 表，权威存储）
        with get_conn() as conn:
            user_msg_id = conn.execute(
                "INSERT INTO messages (user_id, session_id, role, content) "
                "VALUES (%s, %s, 'user', %s) RETURNING message_id",
                (user_id, session_id, user_input),
            ).fetchone()[0]
            ai_msg_id = conn.execute(
                "INSERT INTO messages (user_id, session_id, role, content) "
                "VALUES (%s, %s, 'assistant', %s) RETURNING message_id",
                (user_id, session_id, ai_output),
            ).fetchone()[0]
            conn.execute(
                "UPDATE sessions SET message_count = message_count + 2, "
                "last_message_at = now(), updated_at = now() "
                "WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
            conn.commit()

        # 2. 精筛层：两条消息逐条嵌入写入 message_embeddings（失败仅告警，不影响原文存储）
        self.vector_store.add_message_embedding(user_msg_id, user_id, session_id, None, "user", user_input)
        self.vector_store.add_message_embedding(ai_msg_id, user_id, session_id, None, "assistant", ai_output)

        # 3. 粗筛层：未归档消息攒满一个块（block_rounds 轮）就压缩成摘要块
        self._maybe_create_block(user_id, session_id)

    def get_history(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """获取会话上下文（窗口消息 + 分层摘要 + 格式化全文），返回结构与原实现一致"""
        # 1. 滑动窗口：最近 window_k*2 条消息（SQL 查询，无需裁剪存储）
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE user_id = %s AND session_id = %s "
                "ORDER BY message_id DESC LIMIT %s",
                (user_id, session_id, self.window_k * 2),
            ).fetchall()
        rows.reverse()  # 转回时间正序
        window_messages: List[BaseMessage] = [
            HumanMessage(content=c) if r == "user" else AIMessage(content=c)
            for r, c in rows
        ]

        # 2. 分层摘要：第1层最近2条、第2层最近1条、第3层最新1条
        layer1 = self._load_summaries(user_id, session_id, 1, limit=2)
        layer2 = self._load_summaries(user_id, session_id, 2, limit=1)
        layer3 = self._load_summaries(user_id, session_id, 3, limit=1)

        # 3. 组装（格式与原实现保持一致）
        summary_parts = []
        summary_parts.extend([f"[近期摘要] {s}" for s in layer1])
        if layer2:
            summary_parts.append(f"[中期摘要] {layer2[-1]}")
        if layer3:
            summary_parts.append(f"[长期摘要] {layer3[-1]}")

        return {
            "window_messages": window_messages,
            "summaries": summary_parts,
            "full_context": self._format_context(window_messages, summary_parts),
        }

    def clear_session(self, session_id: str, user_id: str) -> None:
        """清除会话全部数据。[DB改造] 原实现清空 JSON 文件；现删除会话行，子表由外键级联删除"""
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = %s AND user_id = %s",
                         (session_id, user_id))
            conn.commit()
        logger.info(f"[DB改造] 会话已清除: user={user_id}, session={session_id}")

    # ==================================================================
    # 内部：用户/会话自动创建
    # ==================================================================
    def _ensure_user_session(self, user_id: str, session_id: str) -> None:
        """首次消息时自动创建用户与会话行（当前前端固定 u001/s001，无注册接口）。"""
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (user_id) VALUES (%s) "
                "ON CONFLICT (user_id) DO UPDATE "
                "SET last_active_at = now(), updated_at = now(), is_active = TRUE",
                (user_id,),
            )
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, session_type, status) "
                "VALUES (%s, %s, 'chat', 'active') "
                "ON CONFLICT (session_id) DO NOTHING",
                (session_id, user_id),
            )
            conn.commit()

    # ==================================================================
    # 内部：摘要块（粗筛层，按重建文档补齐——原代码没有块概念）
    # ==================================================================
    def _maybe_create_block(self, user_id: str, session_id: str) -> None:
        """未归档消息攒满 block_rounds*2 条时：LLM 生成块摘要 → summary_blocks 落库 → 回填 block_id"""
        block_size = self.block_rounds * 2
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT message_id, role, content FROM messages "
                "WHERE user_id = %s AND session_id = %s AND block_id IS NULL "
                "ORDER BY message_id ASC LIMIT %s",
                (user_id, session_id, block_size),
            ).fetchall()
        if len(rows) < block_size:
            return

        msgs = [
            HumanMessage(content=c) if r == "user" else AIMessage(content=c)
            for _, r, c in rows
        ]
        block_summary = self._generate_summary(msgs)
        if not block_summary:
            return

        block_id = f"blk_{uuid.uuid4().hex}"
        start_id, end_id = rows[0][0], rows[-1][0]
        # 块落库（含块摘要向量；keywords 预留为空，后端尚未设计关键词提取）
        if not self.vector_store.add_block(block_id, user_id, session_id, block_summary,
                                           start_id, end_id, len(rows)):
            return

        with get_conn() as conn:
            conn.execute(
                "UPDATE messages SET block_id = %s, updated_at = now() "
                "WHERE user_id = %s AND session_id = %s "
                "AND message_id BETWEEN %s AND %s AND block_id IS NULL",
                (block_id, user_id, session_id, start_id, end_id),
            )
            conn.execute(
                "UPDATE message_embeddings SET block_id = %s "
                "WHERE user_id = %s AND session_id = %s "
                "AND message_id BETWEEN %s AND %s",
                (block_id, user_id, session_id, start_id, end_id),
            )
            conn.commit()

        # 第1层摘要 = 单块摘要（与重建文档"第1层：单块摘要"一致）
        self._add_summary_to_layer(user_id, session_id, layer=1, content=block_summary,
                                   block_id=block_id, start_id=start_id, end_id=end_id,
                                   count=len(rows))

    # ==================================================================
    # 内部：三层摘要（summaries 表，替代 history_re 的 layer 文件）
    # ==================================================================
    def _add_summary_to_layer(self, user_id: str, session_id: str, layer: int, content: str,
                              block_id: Optional[str] = None, start_id: Optional[int] = None,
                              end_id: Optional[int] = None, count: int = 0) -> None:
        """写入一条摘要，并检查是否触发合并到上一层（每满 merge_threshold 条合并，合并后删除本层那几条）"""
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO summaries (user_id, session_id, block_id, layer, content, "
                "start_message_id, end_message_id, message_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, session_id, block_id, layer, content, start_id, end_id, count),
            )
            conn.commit()

        if layer >= 3:
            return  # 第3层是最浓缩层，不再合并（多条并存，读取时取最新）

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT summary_id, content, start_message_id, end_message_id, message_count "
                "FROM summaries WHERE user_id = %s AND session_id = %s AND layer = %s "
                "ORDER BY summary_id ASC",
                (user_id, session_id, layer),
            ).fetchall()

        if len(rows) >= self.merge_threshold:
            merged = self._merge_summaries([r[1] for r in rows])
            if merged:
                start_vals = [r[2] for r in rows if r[2] is not None]
                end_vals = [r[3] for r in rows if r[3] is not None]
                merged_start = min(start_vals) if start_vals else None
                merged_end = max(end_vals) if end_vals else None
                merged_count = sum(r[4] for r in rows)
                # 删除被合并的本层摘要（与原实现"清空当前层"语义一致）
                with get_conn() as conn:
                    conn.execute(
                        "DELETE FROM summaries WHERE summary_id = ANY(%s)",
                        ([r[0] for r in rows],),
                    )
                    conn.commit()
                # 递归写入上一层
                self._add_summary_to_layer(user_id, session_id, layer + 1, merged,
                                           block_id=None, start_id=merged_start,
                                           end_id=merged_end, count=merged_count)

    def _load_summaries(self, user_id: str, session_id: str, layer: int,
                        limit: Optional[int] = None) -> List[str]:
        """读取指定层最近 limit 条摘要（时间正序返回）"""
        sql = ("SELECT content FROM summaries "
               "WHERE user_id = %s AND session_id = %s AND layer = %s "
               "ORDER BY summary_id DESC")
        params: List[Any] = [user_id, session_id, layer]
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        contents = [r[0] for r in rows]
        contents.reverse()
        return contents

    # ==================================================================
    # LLM 摘要工具方法（与原 ShotMemory 实现一致，仅存储位置变化）
    # ==================================================================
    def _compress_text(self, text: str, purpose: str) -> str:
        """
        通用文本压缩方法，将长文本或摘要列表压缩成更简洁的摘要
        Args:
            text: 待压缩的原始文本（可以是对话内容，也可以是已有的多条摘要）
            purpose: 压缩目的，用于选择提示词，可选 "summarize" 或 "merge"
        """
        if not text or not text.strip():
            return ""

        prompts = self.prompt_dict
        prompt_config = prompts.get(purpose)
        if not prompt_config:
            raise ValueError(f"不支持的压缩目的: {purpose}")

        if self.summary_llm:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_config["system"]),
                    ("human", prompt_config["human"])
                ])
                chain = prompt | self.summary_llm
                result = chain.invoke({"text": text})
                return result.content
            except Exception as e:
                logger.error(f"_compress_text 压缩失败 (目的: {purpose}): {e}")

        # 降级方案：简单截断
        return text[:100] + "..." if len(text) > 100 else text

    def _generate_summary(self, messages: List[BaseMessage]) -> Optional[str]:
        """生成单条摘要（需要外部注入LLM）"""
        if not messages:
            return None
        text = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])
        return self._compress_text(text, purpose="summarize")

    def _merge_summaries(self, summaries: List[str]) -> str:
        """合并多条摘要为一条更浓缩的摘要"""
        if not summaries:
            return ""
        if len(summaries) == 1:
            return summaries[0]
        combined = "\n".join(summaries)
        return self._compress_text(combined, purpose="merge")

    # ==================================================================
    # 工具方法
    # ==================================================================
    def _format_context(self, window_messages: List[BaseMessage], summaries: List[str]) -> str:
        """将窗口消息和摘要格式化为统一文本（与原实现一致）"""
        lines = summaries.copy()
        for msg in window_messages:
            role = "用户" if msg.type == "human" else "助手"
            lines.append(f"{role}：{msg.content}")
        return "\n".join(lines)


memory_service = PgMemory()  # 后续改为懒加载统一服务类示例创建

if __name__ == "__main__":
    memory_service.clear_session(user_id="u001", session_id="s001")
