"""
FastAPI 入口 - Agent 长期记忆系统。

⚠️ **2026-07-22 重要提示**：原服务 `MemoryManager` 默认使用
`MockLLMConsolidator`（基于关键词重叠 + 截断的整合，不是真 LLM）。
本版本启动时检查 `CONSOLIDATOR_PROVIDER` 环境变量。

启动示例：
    # Mock consolidator (本地测试；只能基于 keyword 聚类)
    export CONSOLIDATOR_PROVIDER=keyword
    uvicorn app.main:app

    # 真 LLM (推荐) — 需要实现 LLMConsolidator 类
    export CONSOLIDATOR_PROVIDER=openai
    export OPENAI_API_KEY=sk-xxx
    uvicorn app.main:app

    # 默认 keyword 整合器 + WARNING（开发场景可接受）
    unset CONSOLIDATOR_PROVIDER   # 默认 keyword
"""

import logging
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

_CONSOLIDATOR_PROVIDER = os.getenv("CONSOLIDATOR_PROVIDER", "keyword").lower()


def _warn_if_mock_consolidator():
    if _CONSOLIDATOR_PROVIDER == "keyword":
        logger.warning("=" * 60)
        logger.warning("  ⚠️  CONSOLIDATOR_PROVIDER=keyword (默认)")
        logger.warning("  记忆整合基于关键词重叠 + 截断，不是真 LLM 摘要")
        logger.warning("  生产部署建议：CONSOLIDATOR_PROVIDER=openai")
        logger.warning("=" * 60)
    elif _CONSOLIDATOR_PROVIDER == "openai":
        logger.info("CONSOLIDATOR_PROVIDER=openai — 使用 LLMConsolidator")
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY 未设置，LLM 整合将回退到简单模式")


def _build_consolidator():
    """根据 CONSOLIDATOR_PROVIDER 选择整合器。"""
    if _CONSOLIDATOR_PROVIDER == "openai":
        from manager.llm_consolidator import LLMConsolidator
        return LLMConsolidator()
    # 默认使用 MockLLMConsolidator
    from manager.consolidator import MockLLMConsolidator
    return MockLLMConsolidator()


from manager.memory_manager import MemoryManager


# 全局记忆管理器 — 使用选定的 consolidator
manager = MemoryManager()
manager.consolidator = _build_consolidator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    _warn_if_mock_consolidator()
    # 启动时初始化
    from app.api.memory import set_manager as set_memory_manager
    from app.api.search import set_manager as set_search_manager
    from app.api.agent import set_manager as set_agent_manager

    set_memory_manager(manager)
    set_search_manager(manager)
    set_agent_manager(manager)
    yield
    # 关闭时清理（如有需要）


app = FastAPI(
    title="Agent Long-Term Memory System",
    description="为 AI Agent 提供持久化的长期记忆能力，支持记忆的存储/检索/遗忘/整合。",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS（2026-07-22: 收紧）
_cors_origins = os.getenv("MEMORY_CORS_ORIGINS", "").split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    logger.warning("MEMORY_CORS_ORIGINS 未配置，CORS 中间件未启用")

# 注册路由
from app.api.memory import router as memory_router
from app.api.search import router as search_router
from app.api.agent import router as agent_router

app.include_router(memory_router)
app.include_router(search_router)
app.include_router(agent_router)


@app.get("/")
async def root():
    return {
        "name": "Agent Long-Term Memory System",
        "version": "1.0.0",
        "docs": "/docs",
        "consolidator_provider": _CONSOLIDATOR_PROVIDER,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "consolidator_provider": _CONSOLIDATOR_PROVIDER,
    }