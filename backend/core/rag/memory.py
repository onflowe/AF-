"""短期持久化 长期(vector_store)"""
import os,json
from typing import List, Optional
from datetime import datetime

from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from backend.utils.config_handle import rag_config
from backend.utils.path_tool import get_abs_path
from backend.utils.log_handle import logger
from backend.models.model_factory import chat_model
from backend.utils.prompt_handle import load_memory_sum_prompt
from backend.core.rag.vetot_store import VectorstoreService


class ShotMemory:
    def __init__(self):
        self.window_k = rag_config["window_k"]      #滑动窗口大小
        self.history_dir =get_abs_path(rag_config["history_dir"]) #存储路径
        self.data_re =get_abs_path(rag_config["data_re"])  #总结存储路径
        self.vector_store = VectorstoreService()
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.data_re, exist_ok=True)

        #摘要总结相关
        self.merge_threshold = 3  # 积累多少条摘要后触发合并
        self.summary_llm = chat_model  # 可以后续注入一个LLM实例用于生成摘要
        self.prompt_txt =load_memory_sum_prompt()
        self.prompt_dir =json.loads(self.prompt_txt)


    #获取memary对象
    def get_memory(self,session_id: str):
        #定义会话文件存储路径
        file_path = os.path.join(self.history_dir, f"{session_id}.json")

        #生成存储实例
        return FileChatMessageHistory(file_path)




    #写入数据
    def add_message(self,session_id: str, user_input:str ,ai_output):
        #创建memary实例
        memory = self.get_memory(session_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #存入对话并包装成JSON
        memory.add_messages([
            HumanMessage(content=user_input, type="human",additional_kwargs={"timestamp": now}),
            AIMessage(content=ai_output, type="ai",additional_kwargs={"timestamp": now})
        ])

        # 2. 检查是否需要触发摘要生成
        all_messages = memory.messages
        total_count = len(all_messages)
        keep_count = self.window_k * 2
        sync_threshold = 20  # 同步阈值

        # 判断：是否需要同步？
        need_sync = total_count >= sync_threshold

        # 判断：是否超过了滑动窗口？
        need_trim = total_count > keep_count

        if need_trim:
            removed_messages = all_messages[:-keep_count]
            if removed_messages:
                # 溢出对话生成摘要
                new_summary = self._generate_summary(removed_messages)
                if new_summary:
                    self._add_summary_to_layer(session_id, 1,new_summary)

            # =========条件2：达到同步阈值 → 全量加载原始对话存入向量库【独立执行】=========
        if need_sync:
            # load_document：读取当前会话完整对话，写入向量库长期记忆
            self.vector_store.load_document()
            # 覆盖本地文件，仅保留窗口内最新消息
            remain_messages = all_messages[-keep_count:]
            self._overwrite_messages(session_id, remain_messages)

    #获得历史数据
    def get_history_str(self,session_id: str):
        memory = self.get_memory(session_id)
        #拿到所有的message列表
        all_messages = memory.messages
        #窗口*2 =message个数
        keep_msg_count = self.window_k * 2
        window_messages = all_messages[-keep_msg_count:] if len(all_messages) > keep_msg_count else all_messages

        # 2. 加载分层摘要
        layer1 = self._load_summaries(session_id, 1)  # 最近3条详细摘要
        layer2 = self._load_summaries(session_id, 2)  # 最近3条中等摘要
        layer3 = self._load_layer3_summary(session_id)  # 1条最浓缩摘要

        # 3. 组装：按层级拼接，让最近的、最详细的排在前面
        summary_parts = []
        summary_parts.extend([f"[近期摘要] {s}" for s in layer1[-2:]])  # 只取最近2条，避免过长
        if layer2:
            summary_parts.append(f"[中期摘要] {layer2[-1]}")
        if layer3:
            summary_parts.append(f"[长期摘要] {layer3}")

        # 4. 返回组合结果（包含窗口消息和摘要）
        return {
            "window_messages": window_messages, # Messages []
            "summaries": summary_parts,         # []
            "full_context": self._format_context(window_messages, summary_parts)  # str
        }

    #清除buffer缓存，覆盖JSON为空
    def clear_session(self, session_id: str):
        memory = self.get_memory(session_id)
        memory.clear()

    # 总结摘要服务=========================================================================================================

    def _compress_text(self, text: str, purpose: str) -> str:
        """
        通用文本压缩方法，将长文本或摘要列表压缩成更简洁的摘要
        Args:
            text: 待压缩的原始文本（可以是对话内容，也可以是已有的多条摘要）
            purpose: 压缩目的，用于选择提示词，可选 "summarize" 或 "merge"

        Returns:
            压缩后的摘要文本
        """
        if not text or not text.strip():
            return ""

        # 根据目的选择提示词
        prompts = self.prompt_dir

        prompt_config = prompts.get(purpose)
        if not prompt_config:
            raise ValueError(f"不支持的压缩目的: {purpose}")

        # 如果有注入的LLM，使用它
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

        # 拼接消息内容
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


    def _add_summary_to_layer(self, session_id: str, layer: int, summary: str):
        """添加摘要到指定层，并检查是否需要触发合并"""
        layer_file = self._get_layer_file(session_id, layer)

        # 读取现有摘要列表
        summaries = self._load_summaries(session_id, layer)
        summaries.append(summary)

        # 如果达到合并阈值，触发合并到上一层
        if len(summaries) >= self.merge_threshold and layer < 3:
            # 合并这3条摘要
            merged = self._merge_summaries(summaries)
            # 存入上一层
            if layer + 1 == 3:
                # 第三层特殊处理：直接保存，不进行列表操作
                self._save_layer3_summary(session_id, merged)
            else:
                # 非第三层，继续使用现有逻辑
                self._add_summary_to_layer(session_id, layer + 1, merged)
                # 清空当前层
                self._save_summaries(session_id, layer, [])
        else:
            # 未达到阈值，直接保存
            self._save_summaries(session_id, layer, summaries)

    def _overwrite_messages(self, session_id: str, messages: List[BaseMessage]):
        """覆盖窗口消息（用于滑动窗口更新）"""
        file_path = os.path.join(self.history_dir, f"{session_id}.json")
        # 直接重写文件
        history = FileChatMessageHistory(file_path)
        history.clear()
        history.add_messages(messages)

    def _format_context(self, window_messages: List[BaseMessage], summaries: List[str]) -> str:
        """将窗口消息和摘要格式化为统一文本（用于旧接口兼容）"""
        lines = summaries.copy()
        for msg in window_messages:
            role = "用户" if msg.type == "human" else "助手"
            lines.append(f"{role}：{msg.content}")
        return "\n".join(lines)

    def _get_layer_file(self, session_id: str, layer: int) -> str:
        """获取分层摘要文件路径"""
        suffix = "txt" if layer == 3 else "json"
        return os.path.join(self.data_re, f"{session_id}_layer{layer}.{suffix}")

    def _load_summaries(self, session_id: str, layer: int) -> List[str]:
        """加载指定层的摘要列表（第1、2层）"""
        if layer == 3:
            # 第3层是单条文本，在另一个方法中处理
            return []

        layer_file = self._get_layer_file(session_id, layer)
        if os.path.exists(layer_file):
            try:
                with open(layer_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except:
                return []
        return []

    def _save_summaries(self, session_id: str, layer: int, summaries: List[str]):
        """保存指定层的摘要列表（第1、2层）"""
        if layer == 3:
            # 第3层在单独的方法中处理
            return

        layer_file = self._get_layer_file(session_id, layer)
        with open(layer_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)

    def _load_layer3_summary(self, session_id: str) -> Optional[str]:
        """加载第3层摘要（单条文本）"""
        layer_file = self._get_layer_file(session_id, 3)
        if os.path.exists(layer_file):
            try:
                with open(layer_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                return None
        return None

    def _save_layer3_summary(self, session_id: str, summary: str):
        """保存第3层摘要（覆盖）"""
        layer_file = self._get_layer_file(session_id, 3)
        with open(layer_file, 'w', encoding='utf-8') as f:
            f.write(summary)

    def _clear_summary_file(self, session_id: str, layer: int):
        """清理指定层的摘要文件"""
        layer_file = self._get_layer_file(session_id, layer)
        if os.path.exists(layer_file):
            os.remove(layer_file)




memory_service = ShotMemory()  #后续改为懒加载统一服务类示例创建

if __name__ == "__main__":

   memory_service.clear_session(session_id="s001")









