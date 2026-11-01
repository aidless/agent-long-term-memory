"""
检索 API - 记忆搜索接口。
"""

from fastapi import APIRouter, HTTPException

from app.models import (
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    MemoryResponse,
    ExtractRequest,
    ExtractResponse,
)

router = APIRouter(prefix="/api/search", tags=["Search & Extract"])

_manager = None


def set_manager(manager):
    global _manager
    _manager = manager


@router.post("/", response_model=SearchResponse)
async def search_memories(req: SearchRequest):
    """混合检索记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    memory_types = [t.value for t in req.memory_types] if req.memory_types else None

    results = _manager.search(
        query=req.query,
        memory_types=memory_types,
        top_k=req.top_k,
        threshold=req.threshold,
    )

    return SearchResponse(
        results=[
            SearchResultResponse(
                memory=MemoryResponse(
                    id=r.memory.id,
                    content=r.memory.content,
                    memory_type=r.memory.memory_type,
                    metadata=r.memory.metadata,
                    created_at=r.memory.created_at,
                    updated_at=r.memory.updated_at,
                    access_count=r.memory.access_count,
                    importance=r.memory.importance,
                ),
                score=round(r.score, 4),
                score_breakdown={k: round(v, 4) for k, v in r.score_breakdown.items()},
            )
            for r in results
        ],
        total=len(results),
        query=req.query,
    )


@router.post("/extract", response_model=ExtractResponse)
async def extract_memories(req: ExtractRequest):
    """从文本中提取记忆。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    result = _manager.extractor.extract(req.text, req.speaker)

    return ExtractResponse(
        memories=[
            {
                "content": m.content,
                "memory_type": m.memory_type,
                "importance": m.importance,
                "confidence": m.confidence,
                "metadata": m.metadata,
            }
            for m in result.memories
        ],
        entities=result.entities,
        relations=result.relations,
        emotions=result.emotions,
        preferences=[
            {
                "content": p.content,
                "memory_type": p.memory_type,
                "importance": p.importance,
                "metadata": p.metadata,
            }
            for p in result.preferences
        ],
    )


@router.post("/extract-and-store", response_model=SearchResponse)
async def extract_and_store(req: ExtractRequest):
    """从文本中提取记忆并存储。"""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Manager not initialized")

    stored = _manager.extract_and_store(req.text, req.speaker)

    return SearchResponse(
        results=[
            SearchResultResponse(
                memory=MemoryResponse(
                    id=item.id,
                    content=item.content,
                    memory_type=item.memory_type,
                    metadata=item.metadata,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    access_count=item.access_count,
                    importance=item.importance,
                ),
                score=1.0,
                score_breakdown={"auto_extracted": 1.0},
            )
            for item in stored
        ],
        total=len(stored),
        query=f"auto-extract: {req.text[:50]}",
    )