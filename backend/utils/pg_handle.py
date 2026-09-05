# [DB改造-新增] PostgreSQL(pgvector) 连接池与数据库初始化
# 原项目没有数据库层，本模块统一提供：
#   get_pool()  - 全局连接池（每连接自动注册 vector 类型）
#   get_conn()  - 连接上下文管理器
#   init_db()   - 幂等初始化：启用 pgvector 扩展 + 执行 sql/schema.sql 建表
import os

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from backend.utils.config_handle import pgsql_config
from backend.utils.path_tool import get_abs_path
from backend.utils.log_handle import logger

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """获取全局连接池（懒加载单例）。configure 回调保证池中每个连接都注册了 vector 类型。"""
    global _pool
    if _pool is None:
        conninfo = (
            f"host={pgsql_config['host']} port={pgsql_config['port']} "
            f"dbname={pgsql_config['database']} user={pgsql_config['user']} "
            f"password={pgsql_config['password']}"
        )
        _pool = ConnectionPool(
            conninfo,
            min_size=pgsql_config.get("pool_min_size", 1),
            max_size=pgsql_config.get("pool_max_size", 4),
            open=True,
            configure=register_vector,  # pgvector: 每个连接注册 vector 类型
        )
        logger.info("[DB改造] PostgreSQL 连接池创建成功: %s:%s/%s",
                    pgsql_config['host'], pgsql_config['port'], pgsql_config['database'])
    return _pool


def get_conn():
    """连接上下文管理器：with get_conn() as conn: ..."""
    return get_pool().connection()


def init_db() -> None:
    """幂等初始化数据库：启用扩展并按 schema.sql 建表（启动时调用，可重复执行）。"""
    schema_path = get_abs_path("sql/schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    with get_conn() as conn:
        # psycopg 单次 execute 可执行多条语句（无参数占位符，安全）
        conn.execute(ddl)
        conn.commit()
    logger.info("[DB改造] 数据库初始化完成（扩展+建表）: %s", schema_path)


if __name__ == "__main__":
    init_db()
    print("init_db 执行完毕")
