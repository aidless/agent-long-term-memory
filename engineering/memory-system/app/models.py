"""
Pydantic 模型 - API 请求和响应的数据模型。
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class AddMemoryRequest(BaseModel):
    """添加记忆请求。"""
    content: str = Field(..., description="记忆内容", min_length=1)
    memory_type: MemoryType = Field(default=MemoryType.SEMANTIC, description="记忆类型")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性评分")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    category: Optional[str] = Field(default=None, description="分类（语义记忆）")
    emotion: Optional[str] = Field(default=None, description="情感（情景记忆）")
    skill_name: Optional[str] = Field(default=None, description="技能名称（程序记忆）")


class UpdateMemoryRequest(BaseModel):
    """更新记忆请求。"""
    content: Optional[str] = Field(default=None, description="新内容")
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="新重要性")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="更新的元数据")


class SearchRequest(BaseModel):
    """搜索请求。"""
    query: str = Field(..., description="查询文本", min_length=1)
    memory_types: Optional[list[MemoryType]] = Field(default=None, description="限定记忆类型")
    top_k: int = Field(default=10, ge=1, le=100, description="返回数量")
    threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="最低分数阈值")


class ExtractRequest(BaseModel):
    """记忆提取请求。"""
    text: str = Field(..., description="待提取的文本", min_length=1)
    speaker: str = Field(default="user", description="说话人")


class MemoryResponse(BaseModel):
    """记忆响应。"""
    id: str
    content: str
    memory_type: str
    metadata: dict[str, Any] = {}
    created_at: float
    updated_at: float
    access_count: int
    importance: float


class SearchResultResponse(BaseModel):
    """搜索结果响应。"""
    memory: MemoryResponse
    score: float
    score_breakdown: dict[str, float] = {}


class SearchResponse(BaseModel):
    """搜索响应。"""
    results: list[SearchResultResponse]
    total: int
    query: str


class ExtractResponse(BaseModel):
    """提取响应。"""
    memories: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    emotions: list[dict[str, Any]]
    preferences: list[dict[str, Any]]


class StatsResponse(BaseModel):
    """统计信息响应。"""
    semantic_count: int = 0
    episodic_count: int = 0
    procedural_count: int = 0
    working_count: int = 0
    total_long_term: int = 0
    reference_tracker_size: int = 0


class BuildPromptRequest(BaseModel):
    """构建 Prompt 请求。"""
    system_prompt: str = Field(default="你是一个有帮助的AI助手。", description="系统提示")
    user_message: str = Field(..., description="用户消息", min_length=1)
    query: str = Field(default="", description="记忆检索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="检索记忆数量")
    token_budget: int = Field(default=2000, ge=100, le=8000, description="Token 预算")


class BuildPromptResponse(BaseModel):
    """构建 Prompt 响应。"""
    prompt: str
    memory_count: int
    estimated_tokens: int


class MessageResponse(BaseModel):
    """通用消息响应。"""
    message: str
    success: bool = True


class ForgetResponse(BaseModel):
    """遗忘响应。"""
    forgotten_counts: dict[str, int] = {}
    message: str = ""


class ConsolidateResponse(BaseModel):
    """整合响应。"""
    consolidated_count: int = 0
    message: str = ""