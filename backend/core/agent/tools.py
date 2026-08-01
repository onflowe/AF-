from langchain.tools import tool
from backend.core.rag.rag_service import create_rag_service

@tool(description="查询通用知识库，用来查找客观资料、文档信息")
def search_public_knowledge(query: str):
    """查询通用知识库，用来查找客观资料、文档信息"""
    rag_service = create_rag_service()
    return rag_service.rag_summary(query,use_knowledge=True)

@tool(description="查询你和用户之前的历史对话，回忆之前聊过的内容、用户偏好")
def search_chat_memory(query: str):
    """查询你和用户之前的历史对话，回忆之前聊过的内容、用户偏好"""
    rag_service = create_rag_service()
    return rag_service.rag_summary(query,use_memory=True)