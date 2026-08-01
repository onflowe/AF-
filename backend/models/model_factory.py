from abc import ABC, abstractmethod
from typing import Optional


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
        return DashScopeEmbeddings(model=model_config["embedding_model_name"])

chat_model =ChatOenAIFactory().generator()
embedding_model =EmbeddingFactory().generator()