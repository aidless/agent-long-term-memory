"""
Agent 集成 API - Prompt 构建和上下文管理接口。
"""

from fastapi import APIRouter, HTTPException

from app.models import (
    BuildPromptRequest,
    BuildPromptResponse,
    MessageResponse,
)

from agent_integration.prompt_builder import PromptBuilder, PromptConfig, InjectionStrategy
from agent_integration.context_window import ContextWindowManager, ContextWindowConfig

router = APIRouter(prefix="/api/agent", tags=["Agent Integration"])

_manager = None


def set_manager(manager):
    global _manager
    _manager = manager


@router.post("/build-prompt", response_model=BuildPromptResponse)
async def build_prompt(req: BuildPromptRequest):
    """
    构建记忆增强的 Prompt。

    检索相关记忆并构建包含记忆的完整 prompt。
    """
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    # 检索记忆
    query = req.query or req.user_message
    search_results = _manager.search(query=query, top_k=req.top_k)

    # 获取工作记忆上下文
    working_context = _manager.working.get_context_window()

    # 构建 prompt
    config = PromptConfig(token_budget=req.token_budget, top_k=req.top_k)
    builder = PromptBuilder(config=config)

    full_prompt = builder.build_full_prompt(
        system_prompt=req.system_prompt,
        user_message=req.user_message,
        search_results=search_results,
        working_context=working_context,
    )

    return BuildPromptResponse(
        prompt=full_prompt,
        memory_count=len(search_results),
        estimated_tokens=builder.estimate_tokens(full_prompt),
    )


@router.get("/context-window/allocation")
async def get_allocation(max_tokens: int = 4096):
    """获取上下文窗口分配方案。"""
    config = ContextWindowConfig(max_tokens=max_tokens)
    manager = ContextWindowManager(config)
    alloc = manager.allocate()
    return alloc.to_dict()


@router.post("/context-window/check")
async def check_fit(
    system_prompt: str = "",
    memory_text: str = "",
    user_message: str = "",
    max_tokens: int = 4096,
):
    """检查文本是否适合上下文窗口。"""
    config = ContextWindowConfig(max_tokens=max_tokens)
    manager = ContextWindowManager(config)
    fits, total = manager.fits_in_window(system_prompt, memory_text, user_message)
    return {"fits": fits, "total_tokens": total, "max_tokens": max_tokens}


@router.post("/working-memory", response_model=MessageResponse)
async def add_working_memory(text: str, speaker: str = "user"):
    """添加工作记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    items = _manager.add_to_working_from_conversation(text, speaker)
    return MessageResponse(message=f"Added {len(items)} working memory items")


@router.get("/working-memory", response_model=MessageResponse)
async def get_working_memory():
    """获取当前工作记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    context = _manager.working.get_context_window()
    return MessageResponse(message=context or "(empty)")


@router.delete("/working-memory", response_model=MessageResponse)
async def clear_working_memory():
    """清空工作记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    _manager.working.clear()
    return MessageResponse(message="Working memory cleared")


@router.get("/reference/{memory_id}")
async def get_reference_history(memory_id: str):
    """获取记忆的引用历史。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    history = _manager.get_reference_history(memory_id)
    return {"memory_id": memory_id, "references": history}