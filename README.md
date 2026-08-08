```markdown 
# 🤖 AI 聊天伙伴

基于 Live2D 官方 SDK 5-r.4 和 FastAPI 构建的 AI 聊天伙伴项目。支持自定义性格的 Live2D 模型动画、实时对话、记忆系统等功能。

![Live2D Demo](https://img.shields.io/badge/Live2D-SDK%205--r.4-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue)
![Vite](https://img.shields.io/badge/Vite-5.0+-purple)

---

##  AI生成，有些许偏差



---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名
```

### 2. 前端安装与配置

```bash
cd frontend
npm install
```

**⚠️ 重要：放入 Live2D 官方 SDK 文件**
  
- **Framework**：将 Live2D Cubism SDK for Web 中的 `Framework/` 文件夹复制到 `frontend/src/` 下
- **Core**：将 Live2D Cubism SDK for Web 中的 `Core/live2dcubismcore.js` 复制到 `frontend/public/Core/` 下

```
frontend/
├── src/
│   └── Framework/           ← 从 SDK 复制（包含 cubismframework.ts 等）
├── public/
│   └── Core/
│       └── live2dcubismcore.js  ← 从 SDK 复制
```

### 3. 后端安装与配置

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 配置大模型

复制配置文件模板并填入你的模型配置：

```bash
cp config_text backend/config/config.yaml
# 或直接编辑 backend/config/config.yaml
```

参考 `config_text` 格式，填入你的 API Key、模型名称等信息：

```yaml
# backend/config/config.yaml
llm:
  provider: "volcengine"        # 可选: openai, volcengine, azure, local
  volcano:
    api_key: "你的-API-Key"
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    model: "你的-Endpoint-ID"
    temperature: 0.7
    max_tokens: 4096
  # 其他提供商配置...
```

### 5. 启动项目

**启动后端：**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**启动前端：**

```bash
cd frontend
npm run dev
```

访问 `http://localhost:5173` 即可看到 AI 伙伴。

---

## 🎯 核心功能

- **Live2D 模型渲染**：基于官方 SDK 5-r.4，支持 Cubism 5 模型
- **实时对话**：通过 FastAPI 后端调用大模型 API
- **记忆系统**：短期记忆（滑动窗口）+ 长期记忆（向量库）
- **RAG 检索**：支持知识库增强回答
- **情绪驱动**：模型表情随对话情绪变化


---

## 📦 技术栈

| 技术 | 说明 |
| :--- | :--- |
| **前端** | TypeScript + Vite + Live2D SDK 5-r.4 |
| **后端** | Python 3.10+ + FastAPI + LangChain |
| **大模型** | 火山方舟 / OpenAI / 可扩展 |
| **向量库** | ChromaDB (可切换) |
| **记忆** | 

---

## ⚙️ 配置文件说明

`backend/config/config.yaml` 支持以下配置：

| 配置项 | 说明 |
| :--- | :--- |
| `llm.provider` | 模型提供商 (openai/volcengine/azure/local) |
| `llm.volcano` | 火山方舟配置 |
| `llm.openai` | OpenAI 配置 |
| `embedding.model` | 嵌入模型名称 |
| `vector_store.type` | 向量库类型 (chroma/faiss/pgvector) |
| `memory.window_k` | 短期记忆窗口大小 |
| `rag.chunk_size` | RAG 分块大小 |
| `logging.level` | 日志级别 |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

本项目仅供学习和研究使用。Live2D SDK 的使用请遵守 [Live2D Open Software License](https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html)。

---

## 🙏 致谢

- [Live2D Cubism SDK](https://www.live2d.com/en/download/cubism-sdk/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangChain](https://www.langchain.com/)
- [Vite](https://vitejs.dev/)
```

#还没开发完，以上纯为AI生成模版，欲知详情，可以仔细观看目录
