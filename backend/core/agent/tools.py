from langchain_core.tools import  BaseTool

from backend.core.rag.rag_service import rag_service

from langchain.tools import tool

def create_tool(user_id:str,session_id:str) -> BaseTool:
    #通过工厂函数实时创建工具，以此达到uid和sid的传入
    @tool(description="""
    
    检索知识库与对话历史记忆，辅助回答用户问题。
    参数：
        query：检索关键词
        use_knowledge：是否检索公共知识库。True开启，False关闭。
        use_memory：是否检索本次会话历史对话记忆。True开启，False关闭。
    """)
    def rag_search(query: str,use_knowledge: bool = True,use_memory: bool = True) -> str:

        # user_id、session_id 外部传入
        return rag_service.rag_summary(
            quest=query,
            user_id=user_id,
            session_id=session_id,
            use_knowledge=use_knowledge,
            use_memory=use_memory
        )
    return rag_search
