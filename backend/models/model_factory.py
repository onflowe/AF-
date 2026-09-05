from abc import ABC, abstractmethod
from typing import Optional, List
import os


from langchain_core.embeddings import  Embeddings
from langchain_core.language_models import BaseChatModel
from  langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import ChatOpenAI

from backend.utils.config_handle import model_config

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass

class ChatOenAIFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatOpenAI(model=model_config["model_name"],base_url=model_config["base_url"],api_key=model_config["api_key"])

class EmbeddingFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        # [DB改造] 嵌入模型需要 DashScope API Key。原实现只写 DashScopeEmbeddings(model=...)，
        # 完全依赖环境变量 DASHSCOPE_API_KEY（缺失时构造即报错）。
        # 新实现：优先读 config/model.yml 的 embedding_api_key，其次读环境变量 DASHSCOPE_API_KEY。
        # 向量维度由模型决定：text-embedding-v4 输出 1024 维，与 sql/schema.sql 中 vector(1024) 一致。
        api_key = model_config.get("embedding_api_key") or os.environ.get("DASHSCOPE_API_KEY")
        kwargs = {"model": model_config["embedding_model_name"]}
        if api_key:
            kwargs["dashscope_api_key"] = api_key
        return DashScopeEmbeddings(**kwargs)


class _LazyEmbeddings(Embeddings):
    """[DB改造-新增] 嵌入模型懒加载代理：
    原代码在模块导入时就构造嵌入模型，Key 缺失会导致整个后端无法启动；
    懒加载后，无 Key 时后端可正常启动（对话/消息存储不受影响），
    仅向量检索/写入降级（调用处会捕获异常并记录日志，见 vector_store._embed）。"""

    def __init__(self):
        self._model: Optional[Embeddings] = None
        self._error: Optional[Exception] = None

    def _get(self) -> Embeddings:
        if self._model is None and self._error is None:
            try:
                self._model = EmbeddingFactory().generator()
            except Exception as e:
                self._error = e
        if self._error is not None:
            raise RuntimeError(
                "[DB改造] 嵌入模型初始化失败：未配置 DashScope API Key。"
                "请在 config/model.yml 的 embedding_api_key 填写，"
                "或设置环境变量 DASHSCOPE_API_KEY。原始错误: %s" % self._error
            )
        return self._model

    def embed_query(self, text: str) -> List[float]:
        return self._get().embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._get().embed_documents(texts)


chat_model =ChatOenAIFactory().generator()
embedding_model = _LazyEmbeddings()  # [DB改造] 由直接构造改为懒加载代理