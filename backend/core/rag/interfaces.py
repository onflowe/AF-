# backend/core/rag/interfaces.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from langchain_core.messages import BaseMessage


class IMemoryService(ABC):
    """
    记忆服务抽象接口
    所有记忆存储实现（文件、数据库、Redis等）都必须实现此接口
    """
    
    @abstractmethod
    def add_message(self, user_id: str, session_id: str, user_input: str, ai_output: str) -> None:
        """
        添加一条对话消息到记忆
        """
        pass
    
    @abstractmethod
    def get_history(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """
        获取会话的完整上下文（包含窗口消息和摘要）
        返回格式：
        {
            "window_messages": List[BaseMessage],  # 窗口内的消息对象
            "summaries": List[str],                # 分层摘要
            "full_context": str                    # 格式化的完整上下文
        }
        """
        pass
    
    @abstractmethod
    def clear_session(self, user_id: str, session_id: str) -> None:
        """
        清除会话的所有记忆数据
        """
        pass
    
    