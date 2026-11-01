# Agent 长期记忆系统

为 AI Agent 提供持久化的长期记忆能力，支持记忆的存储、检索、遗忘和整合。

## 架构设计

本项目参考人类记忆系统，实现了四种记忆类型：

| 记忆类型 | 说明 | 存储方式 | 持久化 |
|---------|------|---------|--------|
| 语义记忆 (Semantic) | 事实和知识 | TF-IDF 向量存储 | JSON 文件 |
| 情景记忆 (Episodic) | 交互和经历 | TF-IDF 向量存储 | JSON 文件 |
| 程序记忆 (Procedural) | 技能和模式 | TF-IDF 向量存储 | JSON 文件 |
| 工作记忆 (Working) | 短期上下文 | 内存 OrderedDict | 不持久化 |

## 核心功能

### 记忆管理
- **写入**: 手动添加 + 从对话自动提取
- **检索**: 语义相似度 + 时间衰减 + 重要性评分的混合检索
- **更新/合并**: 支持记忆内容、元数据、重要性的更新
- **遗忘**: 基于指数衰减函数和容量限制的自动遗忘
- **整合**: LLM 辅助（Mock）的归纳总结，将多条相关记忆合并

### 检索策略
- **语义检索**: 基于 TF-IDF + 余弦相似度
- **时间衰减**: 指数衰减函数 `score = exp(-lambda * age)`
- **重要性评分**: `alpha * manual + beta * access_freq + gamma * recency`
- **混合检索**: 默认权重 语义*0.5 + 时间*0.2 + 重要性*0.3
- **关联记忆**: 一次检索触发相关记忆的二次检索

### Agent 集成
- Token 预算控制的 Prompt 构建
- 上下文窗口管理和自动截断
- 三种注入策略: Top-K / 阈值 / 相关性
- 记忆引用追踪

## 项目结构

```
18-agent-long-term-memory/
├── app/                    # FastAPI 应用层
│   ├── api/                # API 路由
│   │   ├── memory.py       # 记忆 CRUD
│   │   ├── search.py       # 检索和提取
│   │   └── agent.py        # Agent 集成
│   ├── main.py             # FastAPI 入口
│   └── models.py           # Pydantic 模型
├── memory/                 # 记忆类型
│   ├── base.py             # 基类和 MemoryItem
│   ├── semantic.py         # 语义记忆
│   ├── episodic.py         # 情景记忆
│   ├── procedural.py       # 程序记忆
│   └── working.py          # 工作记忆
├── manager/                # 记忆管理
│   ├── memory_manager.py   # 统一管理接口
│   ├── extractor.py        # 记忆提取（规则 + Mock LLM）
│   ├── consolidator.py     # 记忆整合（Mock LLM）
│   └── forgetter.py        # 记忆遗忘
├── retrieval/              # 检索策略
│   ├── semantic_search.py  # 语义检索
│   ├── time_decay.py       # 时间衰减
│   ├── importance.py       # 重要性评分
│   └── hybrid.py           # 混合检索
├── agent_integration/      # Agent 集成
│   ├── prompt_builder.py   # Prompt 构建
│   └── context_window.py   # 上下文窗口
├── vector_store/           # 向量存储
│   └── simple_vector.py    # TF-IDF + JSON 持久化
├── tests/                  # 测试
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行测试

```bash
pytest tests/ -v
```

### 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看交互式 API 文档。

### Docker 部署

```bash
docker-compose up --build
```

## API 概览

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | /api/memory/ | 添加记忆 |
| GET | /api/memory/stats | 统计信息 |
| GET | /api/memory/{type}/{id} | 获取记忆 |
| PUT | /api/memory/{type}/{id} | 更新记忆 |
| DELETE | /api/memory/{type}/{id} | 删除记忆 |
| POST | /api/memory/forget | 执行遗忘 |
| POST | /api/memory/consolidate | 整合记忆 |
| POST | /api/search/ | 混合检索 |
| POST | /api/search/extract | 提取记忆 |
| POST | /api/search/extract-and-store | 提取并存储 |
| POST | /api/agent/build-prompt | 构建增强 Prompt |
| GET | /api/agent/context-window/allocation | 窗口分配 |
| POST | /api/agent/working-memory | 添加工作记忆 |
| GET | /api/agent/working-memory | 获取工作记忆 |

## 技术栈

- **Python 3.11+**
- **FastAPI** - Web 框架
- **Pydantic** - 数据验证
- **NumPy** - 向量计算
- **scikit-learn** - （预留，可用于更高级的相似度计算）