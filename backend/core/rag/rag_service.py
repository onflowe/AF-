from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from backend.core.rag.vetot_store import VectorstoreService
from backend.utils.prompt_handle import load_rag_prompt
from backend.models.model_factory import chat_model
from backend.utils.config_handle import rag_config


class RagService:
    def __init__(self):
        self.vector_store =VectorstoreService()
                                                    #获得向量库
        self.prompt_txt = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_txt) #获取提示词模版
        self.model = chat_model #获取查询模型
        self.chain = self._int_chain()                                         # PromptTemplate 是一个可以注入提示词等的模板，可以往里面注入一些提示词需要的变量


    def _int_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()   #以字符串的形式返回
        return chain

    #返回检索得到的文档
    def retrieve_knowledge(self, query: str) -> List[Document]:
        filter_cond = {"type": "knowledge"}
        retriever = self.vector_store.get_retriever(rag_config["k_metadata_type "])
        return retriever.invoke(query)

        # 检索当前用户长期对话记忆 type=chat_memory

    def retrieve_chat_memory(self, query: str, k=3) -> List[Document]:
        retriever = self.vector_store.get_retriever(rag_config["m_metadata_type"])
        docs = retriever.invoke(query)
        # 对话记忆按时间先后排序，新对话靠前
        docs.sort(key=lambda x: x.metadata.get("msg_time", 0), reverse=True)
        return docs

    #将用户提问和资料注入chain
    def rag_summary(self,quest:str,use_knowledge:bool, use_memory: bool)  :
        docs = []
        if use_knowledge:
            docs.extend(self.retrieve_knowledge(quest))
        if use_memory:
            docs.extend(self.retrieve_chat_memory(quest))
        context = ""
        count = 0
        for doc in docs:
            count += 1
            context += f"参考资料{count}，参考内容为{doc.page_content},元数据为{doc.metadata}\n"
        return self.chain.invoke(
            {
                "input" : quest,
                "context" : context
            }
        )
    """ 考虑历史对话注入时机 """

def create_rag_service():
    rag_service = RagService()
    return rag_service