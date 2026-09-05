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

# [DB改造] 原 load_redis_config / redis_config 已删除（Redis 记忆实现废弃移除）
# [DB改造-新增] PostgreSQL(pgvector) 配置加载
def load_pgsql_config(config_path: str = get_abs_path('config/pgsql.yml'),encoding='utf-8'):
    with open(config_path,'r',encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

model_config = load_model_config()
rag_config = load_rag_config()
prompt_config = load_prompt_config()
pgsql_config = load_pgsql_config()