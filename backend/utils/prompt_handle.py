"""
加载 PROMPT
"""
from backend.utils.path_tool import get_abs_path
from backend.utils.config_handle import prompt_config
from backend.utils.log_handle import logger

def load_system_prompt():
    try:
        path =get_abs_path(prompt_config["system_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompt]没有配置system_prompt_path")
        raise e
    try:
        return open(path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompt]解析提示词出错{str(e)}")
        raise e

def load_rag_prompt():
    try:
        path =get_abs_path(prompt_config["rag_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompt]没有配置rag_prompt_path")
        raise e
    try:
        return open(path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]解析提示词出错{str(e)}")
        raise e

def load_memory_sum_prompt():
    try:
        path =get_abs_path(prompt_config["memorySum_prompt_path"])
    except KeyError as e:
        logger.error(f"[memorySum_prompt_path]没有配置memorySum_prompt_path")
        raise e
    try:
        return open(path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[memorySum_prompt_path]解析提示词出错{str(e)}")
        raise e