-- =====================================================================
-- [DB改造] AF 数据库结构（PostgreSQL 17 + pgvector）
-- 依据《数据库重建.md》生成，并作如下调整（详见《数据库改造说明.md》）：
--   1. 未设计的字段(emotion/emotion_score/intent/topic/importance/is_key_event)
--      全部不建，将来设计确定后再 ALTER TABLE 添加；
--   2. 精筛层不再是"独立外部向量库"，改为本库 message_embeddings 表(pgvector)，
--      冗余保存消息原文，语义检索命中后可直接拿到原文；messages 表仍是
--      消息的权威有序存储，供 SQL 精确查询；
--   3. 原 Chroma 公共知识库改由 knowledge_chunks 表(pgvector)承载；
--   4. 时间列采用 TIMESTAMPTZ（设计文档写 TIMESTAMP，此处用带时区类型更严谨）；
--   5. 向量维度 1024，与当前嵌入模型 text-embedding-v4 输出一致
--      （设计文档写 384/1536 是为其他嵌入方案预留的，未采用）。
-- 本文件可重复执行（全部 IF NOT EXISTS / 幂等）。
-- =====================================================================

-- 1. pgvector 扩展（必须在建表前启用）
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================================
-- 2. users 用户表
-- =====================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id              VARCHAR(64) PRIMARY KEY,                -- 用户唯一标识
    username             VARCHAR(100),                           -- 用户昵称
    email                VARCHAR(255),                           -- 用户邮箱
    objective_profile    JSONB,                                  -- 客观形象：年龄、职业、兴趣等
    ai_perception        JSONB,                                  -- AI对用户的看法：性格、情绪模式
    user_self_perception JSONB,                                  -- 用户自画像：用户如何描述自己
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),     -- 注册时间
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),     -- 画像更新时间
    last_active_at       TIMESTAMPTZ,                            -- 最后活跃时间
    is_active            BOOLEAN NOT NULL DEFAULT TRUE           -- 是否活跃用户
);

CREATE INDEX IF NOT EXISTS idx_users_username   ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email      ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_is_active  ON users (is_active);

-- =====================================================================
-- 3. sessions 会话表
-- =====================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id      VARCHAR(64) PRIMARY KEY,                              -- 会话唯一标识
    user_id         VARCHAR(64) NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    session_name    VARCHAR(200),                                         -- 会话名称
    session_type    VARCHAR(50)  NOT NULL DEFAULT 'chat',                 -- chat/support/planning
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',               -- active/archived/deleted
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ,                                          -- 最后消息时间
    message_count   INTEGER      NOT NULL DEFAULT 0                       -- 消息总数
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id         ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status          ON sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_last_message_at ON sessions (last_message_at);

-- =====================================================================
-- 4. summary_blocks 粗筛层（核心）
--    每 n 轮对话压缩为 1 个块摘要，对块摘要生成向量实现快速粗筛定位
-- =====================================================================
CREATE TABLE IF NOT EXISTS summary_blocks (
    block_id         VARCHAR(64) PRIMARY KEY,                     -- 块唯一标识（应用层生成 blk_xxx）
    user_id          VARCHAR(64) NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    session_id       VARCHAR(64) NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    block_summary    TEXT NOT NULL,                               -- 块摘要（概括n轮对话）
    start_message_id BIGINT,                                      -- 块起始消息ID
    end_message_id   BIGINT,                                      -- 块结束消息ID
    message_count    INTEGER NOT NULL DEFAULT 0,                  -- 块内消息数量
    keywords         TEXT[] NOT NULL DEFAULT '{}',                -- 关键词数组（辅助检索；后端暂未生成，预留）
    embedding        vector(1024),                                -- pgvector 粗筛核心（嵌入失败时为 NULL，见改造说明）
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_blocks_user_session ON summary_blocks (user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_blocks_keywords      ON summary_blocks USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_blocks_embedding     ON summary_blocks USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 5. messages 消息表（数据的唯一权威来源，粒度最细，按轮存两条）
-- =====================================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id BIGSERIAL PRIMARY KEY,                              -- 消息唯一标识
    user_id    VARCHAR(64) NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    block_id   VARCHAR(64) REFERENCES summary_blocks (block_id) ON DELETE SET NULL, -- 所属块（生成块后回填）
    role       VARCHAR(20) NOT NULL,                               -- user/assistant/system
    content    TEXT NOT NULL,                                      -- 消息原文（完整保存）
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_user_session ON messages (user_id, session_id, message_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at  ON messages (created_at);
-- 查"未归档进块"的消息用（块生成逻辑）
CREATE INDEX IF NOT EXISTS idx_messages_unblocked   ON messages (session_id, message_id) WHERE block_id IS NULL;

-- =====================================================================
-- 6. summaries 压缩层（三层摘要机制，1→2→3 逐层合并）
-- =====================================================================
CREATE TABLE IF NOT EXISTS summaries (
    summary_id       BIGSERIAL PRIMARY KEY,
    user_id          VARCHAR(64) NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    session_id       VARCHAR(64) NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    block_id         VARCHAR(64) REFERENCES summary_blocks (block_id) ON DELETE SET NULL, -- 来源块（仅第1层）或NULL
    layer            INTEGER NOT NULL CHECK (layer IN (1, 2, 3)),  -- 层级 1/2/3
    content          TEXT NOT NULL,
    start_message_id BIGINT,                                       -- 覆盖的起始消息
    end_message_id   BIGINT,                                       -- 覆盖的结束消息
    message_count    INTEGER NOT NULL DEFAULT 0,                   -- 覆盖的消息数
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_summaries_user_session_layer ON summaries (user_id, session_id, layer, summary_id);

-- =====================================================================
-- 7. message_embeddings 精筛层（原"独立向量库"改为此表）
--    每条消息一条向量 + 冗余原文，语义检索命中即得原文；
--    messages 表则负责结构化的精确查询（按时间/角色/块等）。
-- =====================================================================
CREATE TABLE IF NOT EXISTS message_embeddings (
    embedding_id BIGSERIAL PRIMARY KEY,
    message_id   BIGINT NOT NULL UNIQUE REFERENCES messages (message_id) ON DELETE CASCADE, -- 对应消息
    user_id      VARCHAR(64) NOT NULL,
    session_id   VARCHAR(64) NOT NULL,
    block_id     VARCHAR(64),                                     -- 冗余关联块（生成块后回填）
    role         VARCHAR(20) NOT NULL,
    content      TEXT NOT NULL,                                   -- 消息原文（冗余，检索直接返回）
    embedding    vector(1024) NOT NULL,                           -- 单条消息语义向量
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_msgemb_user_session ON message_embeddings (user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_msgemb_embedding    ON message_embeddings USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 8. knowledge_chunks 公共知识库（替代原 Chroma 知识库）
--    data/ 下的 txt/json 文档分块后入库，source_md5+chunk_index 去重
-- =====================================================================
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id    BIGSERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,                                    -- 来源文件路径
    source_md5  TEXT NOT NULL,                                    -- 来源文件MD5（去重，替代原 md5.txt）
    chunk_index INTEGER NOT NULL,                                 -- 文件内分块序号
    content     TEXT NOT NULL,
    embedding   vector(1024) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_md5, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
