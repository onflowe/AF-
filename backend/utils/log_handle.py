import logging
from backend.utils.path_tool import get_abs_path
import os
from datetime import datetime

# 日志保存根目录
LOG_ROOT = get_abs_path("logs")

# 确保日志存在
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志的格式配置
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)  # 日志时间 -  文件 - 级别 - 所在文件：行数 - 内容


# 获得一个日志控制器
def get_logger(
        name: str = "agent",
        console_leve: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file=None
) -> logging.Logger:
    # 创建一个对象
    logger = logging.getLogger(name)  # logger决定要记录的日志，handler决定输出
    # 设置级别
    logger.setLevel(logging.DEBUG)  # 记录的级别，debug最低级，即全部

    # 避免重复添加Handler
    if logger.handlers:
        return logger

    # 控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_leve)  # 输出级别
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)  # 输出格式

    logger.addHandler(console_handler)  # 添加到logger中

    # 文件Handler
    if not log_file:
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)

    return logger


logger = get_logger()