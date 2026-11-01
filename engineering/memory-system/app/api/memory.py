"""
记忆 CRUD API - 记忆的增删改查接口。
"""

from fastapi import APIRouter, HTTPException

from app.models import (
    AddMemoryRequest,
    UpdateMemoryRequest,
    MemoryResponse,
    MessageResponse,
    ForgetResponse,
    ConsolidateResponse,
    StatsResponse,
    MemoryType,
)

router = APIRouter(prefix="/api/memory", tags=["Memory CRUD"])

# 全局 manager 实例在 main.py 中设置
_manager = None


def set_manager(manager):
    global _manager
    _manager = manager


def _to_response(item) -> MemoryResponse:
    """将 MemoryItem 转换为 API 响应。"""
    return MemoryResponse(
        id=item.id,
        content=item.content,
        memory_type=item.memory_type,
        metadata=item.metadata,
        created_at=item.created_at,
        updated_at=item.updated_at,
        access_count=item.access_count,
        importance=item.importance,
    )


@router.post("/", response_model=MemoryResponse)
async def add_memory(req: AddMemoryRequest):
    """添加一条记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    kwargs = {}
    if req.category:
        kwargs["category"] = req.category
    if req.emotion:
        kwargs["emotion"] = req.emotion
    if req.skill_name:
        kwargs["skill_name"] = req.skill_name

    add_fn = {
        MemoryType.SEMANTIC: _manager.add_semantic,
        MemoryType.EPISODIC: _manager.add_episodic,
        MemoryType.PROCEDURAL: _manager.add_procedural,
        MemoryType.WORKING: _manager.add_working,
    }

    fn = add_fn.get(req.memory_type)
    if not fn:
        raise HTTPException(status_code=400, detail=f"Unknown memory type: {req.memory_type}")

    item = fn(content=req.content, importance=req.importance, metadata=req.metadata, **kwargs)
    return _to_response(item)


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """获取记忆系统统计信息。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")
    stats = _manager.get_stats()
    return StatsResponse(**stats)


@router.get("/{memory_type}/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_type: str, memory_id: str):
    """获取指定记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    item = _manager.get_memory(memory_type, memory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_response(item)


@router.put("/{memory_type}/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_type: str, memory_id: str, req: UpdateMemoryRequest):
    """更新记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    kwargs = {}
    if req.content is not None:
        kwargs["content"] = req.content
    if req.importance is not None:
        kwargs["importance"] = req.importance
    if req.metadata is not None:
        kwargs["metadata"] = req.metadata

    item = _manager.update_memory(memory_type, memory_id, **kwargs)
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_response(item)


@router.delete("/{memory_type}/{memory_id}", response_model=MessageResponse)
async def delete_memory(memory_type: str, memory_id: str):
    """删除记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    success = _manager.delete_memory(memory_type, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MessageResponse(message="Memory deleted successfully")


@router.post("/forget", response_model=ForgetResponse)
async def forget_memories():
    """执行遗忘流程。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    result = _manager.forget()
    counts = {k: len(v) for k, v in result.items()}
    total = sum(counts.values())
    return ForgetResponse(
        forgotten_counts=counts,
        message=f"Forgot {total} memories in total",
    )


@router.post("/consolidate", response_model=ConsolidateResponse)
async def consolidate_memories():
    """整合语义记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    consolidated = _manager.consolidate_memories("semantic")
    return ConsolidateResponse(
        consolidated_count=len(consolidated),
        message=f"Consolidated into {len(consolidated)} memories",
    )


@router.delete("/", response_model=MessageResponse)
async def clear_all():
    """清空所有记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")
    _manager.clear_all()
    return MessageResponse(message="All memories cleared")