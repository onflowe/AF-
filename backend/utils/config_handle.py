import yaml
from backend.utils.path_tool import get_abs_path

def load_model_config(config_path: str = get_abs_path('config/model.yml'),encoding='utf-8'):
    with open(config_path,'r',encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_rag_config(config_path: str = get_abs_path('config/rag.yml'),encoding='utf-8'):
    with open(config_path,'r',encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_prompt_config(config_path: str = get_abs_path('config/prompt.yml'),encoding='utf-8'):
    with open(config_path,'r',encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

model_config = load_model_config()
rag_config = load_rag_config()
prompt_config = load_prompt_config()