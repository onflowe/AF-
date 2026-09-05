
import os,json,hashlib
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader

from backend.utils.config_handle import rag_config
from backend.utils.path_tool import get_abs_path
from backend.utils.log_handle import logger


#加载文件
def load_txt(path:str)->List[Document]:
    documents = TextLoader(path,encoding='utf-8').load()
    docs =[]
    #添加metadata
    for doc in documents:
        # [DB改造] 原代码写 doc.metadata["type"] = rag_config["k_metadata_type"]（Chroma 过滤用）；
        # 新实现知识库统一存 knowledge_chunks 表，type 字段随 Chroma 弃用，仅保留来源文件信息
        doc.metadata["source_file"] = path
        docs.append(doc)
    return docs
    #List[Document]

# [DB改造] load_json 已删除：该函数用于解析旧版 history/{uid}/{sid}.json 对话文件并灌入
# Chroma，但从未被任何代码调用（死代码），且 JSON 文件记忆已整体迁移到 messages 表，不再需要。

#寻找文件路径
def load_file_path(data_path,allowed_type):

    all_files = []

    for file in os.listdir(data_path):
        full_path = os.path.join(data_path, file)

        if file.endswith(allowed_type):

            all_files.append(full_path)

        elif os.path.isdir(full_path):

            sub_files =load_file_path(full_path,allowed_type)
            all_files.extend(sub_files)

    return tuple(all_files)

# 将文件转换成MD5值

def get_md5_has(file_path: str):

    # 确保文件存在
    if not os.path.exists(file_path):
        logger.warn(f"[文件加载]{file_path}文件不存在")
        return
    # 是否为文件，
    if not os.path.isfile(file_path):
        logger.warn(f"[文件加载]{file_path}不是文件")
        return
    # 计算MD5
    md5_obj = hashlib.md5()
    # 分块
    chunk_size = 4096
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"[文件加载]{file_path}文件加载失败{str(e)}")
        return

if __name__=="__main__":
    l = load_file_path(get_abs_path(rag_config["data_path"]),rag_config["allowed_type"])
    for path in l:
        print(path)
