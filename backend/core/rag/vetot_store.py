
import os

from backend.utils.file_handle import load_txt,load_file_path,get_md5_has
from backend.utils.path_tool import get_abs_path
from backend.utils.config_handle import rag_config
from backend.utils.log_handle import logger
from backend.models.model_factory import embedding_model


from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

class VectorstoreService:
    def __init__(self):
        #定义一个向量库
        self.vectorstore = Chroma(
            collection_name=rag_config["collection_name"],
            embedding_function= embedding_model,
            persist_directory=get_abs_path(rag_config["persist_directory"])
        )

        #定义一个分隔器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size= rag_config["chunk_size"],
            chunk_overlap=rag_config["chunk_overlap"],
            separators= rag_config["separators"],
            length_function= len
        )


    #输出---调用检索器
    def get_retriever(self,filter_dict:dict=None):
        # 每次查询独立生成过滤条件
        return self.vectorstore.as_retriever(seach_kwargs={"k":rag_config["k"],"filter":filter_dict})

    #输入
    #文档加载

    def load_document(self ,data_path:str):
        #md5去重
        md5_path = get_abs_path(rag_config["md5_hex_store"])
        def check_md5_hex(md5_for_check):
            if not os.path.exists(md5_path):
                open(md5_path, "w", encoding="utf-8").close()
                return False
            with open(md5_path) as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True
                return False

        def save_md5(md5_for_check):
            with open(md5_path, "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        """===============================  文件夹目录传入位置  ============================================================================================================="""
        allowed_path =load_file_path(data_path,rag_config["allowed_type"])

        for path in allowed_path:
            md5_hex = get_md5_has(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[文件加载]:{path}文件已被记录过")
                continue
            try:
                documents =  load_txt(path)
                if not documents:
                    logger.error(f"File empty: {path}")
                    raise
                documents_splitter =self.splitter.split_documents(documents)
                if not documents_splitter:
                    logger.error(f"File splitter empty: {path}")
                    raise
                self.vectorstore.add_documents(documents_splitter)
                save_md5(md5_hex)
                logger.info(f"Document added success: {path}")
            except Exception as e:
                logger.error(f"File found false: {path},{str(e)}")

    #知识库加载
    def load_know(self):
        self.load_document(get_abs_path(rag_config["data_path"]))

            #语义去重

    #对话加载


if __name__=="__main__":
    vec = VectorstoreService()
    vec.load_know()










