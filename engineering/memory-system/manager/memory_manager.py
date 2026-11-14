"""
记忆管理器 - 统一的记忆管理接口。
"""

import time
import logging
from typing import Optional

from memory.base import MemoryItem
from memory.semantic import SemanticMemory
from memory.episodic import EpisodicMemory
from memory.procedural import ProceduralMemory
from memory.working import WorkingMemory
from manager.extractor import MockLLMExtractor
from manager.consolidator import MockLLMConsolidator
from manager.forgetter import MemoryForgetter, ForgetConfig
from manager.conflict import ConflictDetector
from manager.associated_forgetter import AssociatedForgetter
from manager.calibration import (
    ProceduralStalenessDetector,
    ImportanceCalibrator,
)
from retrieval.hybrid import HybridRetriever, HybridConfig
from retrieval.semantic_search import SearchResult

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器 - 统一管理所有类型的记忆。

    提供：
    - 记忆的写入（自动提取 + 手动添加）
    - 记忆的检索（混合检索策略）
    - 记忆的更新和合并
    - 记忆的遗忘
    - 记忆的整合
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        semantic_path: Optional[str] = None,
        episodic_path: Optional[str] = None,
        procedural_path: Optional[str] = None,
        working_capacity: int = 20,
        working_ttl: float = 3600.0,
        hybrid_config: Optional[HybridConfig] = None,
        forget_config: Optional[ForgetConfig] = None,
    ):
        # 初始化四种记忆存储
        self.semantic = SemanticMemory(persist_path=semantic_path)
        self.episodic = EpisodicMemory(persist_path=episodic_path)
        self.procedural = ProceduralMemory(persist_path=procedural_path)
        self.working = WorkingMemory(capacity=working_capacity, ttl_seconds=working_ttl)

        # 检索器
        self.retriever = HybridRetriever(config=hybrid_config)

        # 提取器和整合器
        self.extractor = MockLLMExtractor()
        self.consolidator = MockLLMConsolidator()

        # 遗忘器
        self.forgetter = MemoryForgetter(config=forget_config)

        # 冲突检测器和关联遗忘器（R2.3 缺口补全）
        self.conflict_detector = ConflictDetector()
        self.associated_forgetter = AssociatedForgetter()

        # 程序记忆陈化检测 + 重要性校准（R2.3 剩余缺口补全）
        self.staleness_detector = ProceduralStalenessDetector()
        self.importance_calibrator = ImportanceCalibrator()

        # 记忆引用追踪
        self._reference_tracker: dict[str, list[str]] = {}

    # ==================== 写入操作 ====================

    def add_semantic(self, content: str, importance: float = 0.5, metadata: Optional[dict] = None, **kwargs) -> MemoryItem:
        """添加语义记忆（自动检测冲突）。"""
        item = self.semantic.add(content, metadata=metadata, importance=importance, **kwargs)
        self._auto_conflict_check(item)
        return item

    def add_episodic(self, content: str, importance: float = 0.5, metadata: Optional[dict] = None, **kwargs) -> MemoryItem:
        """添加情景记忆（自动检测冲突）。"""
        item = self.episodic.add(content, metadata=metadata, importance=importance, **kwargs)
        self._auto_conflict_check(item)
        return item

    def add_procedural(self, content: str, importance: float = 0.5, metadata: Optional[dict] = None, **kwargs) -> MemoryItem:
        """添加程序记忆（自动检测冲突）。"""
        item = self.procedural.add(content, metadata=metadata, importance=importance, **kwargs)
        self._auto_conflict_check(item)
        return item

    def add_working(self, content: str, importance: float = 0.5, metadata: Optional[dict] = None, **kwargs) -> MemoryItem:
        """添加工作记忆。"""
        return self.working.add(content, metadata=metadata, importance=importance, **kwargs)

    def add_to_working_from_conversation(self, text: str, speaker: str = "user") -> list[MemoryItem]:
        """从对话中添加到工作记忆。"""
        items = []
        # 直接添加到工作记忆
        item = self.working.add(
            content=f"[{speaker}] {text}",
            metadata={"speaker": speaker},
            importance=0.3,
        )
        items.append(item)
        return items

    def extract_and_store(self, text: str, speaker: str = "user") -> list[MemoryItem]:
        """
        从对话文本中自动提取记忆并存储。

        Args:
            text: 对话文本
            speaker: 说话人

        Returns:
            提取并存储的记忆列表
        """
        result = self.extractor.extract(text, speaker)
        stored = []

        for extracted in result.memories:
            try:
                if extracted.memory_type == "semantic":
                    item = self.semantic.add(
                        content=extracted.content,
                        importance=extracted.importance,
                        metadata=extracted.metadata,
                    )
                elif extracted.memory_type == "episodic":
                    item = self.episodic.add(
                        content=extracted.content,
                        importance=extracted.importance,
                        metadata=extracted.metadata,
                    )
                elif extracted.memory_type == "procedural":
                    item = self.procedural.add(
                        content=extracted.content,
                        importance=extracted.importance,
                        metadata=extracted.metadata,
                    )
                else:
                    continue
                stored.append(item)
            except Exception as e:
                logger.warning(f"Failed to store extracted memory: {e}")

        return stored

    # ==================== 检索操作 ====================

    def search(
        self,
        query: str,
        memory_types: Optional[list[str]] = None,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        混合检索记忆。

        Args:
            query: 查询文本
            memory_types: 限制搜索的记忆类型（None 表示全部）
            top_k: 返回数量
            threshold: 最低分数阈值

        Returns:
            检索结果列表
        """
        # 收集候选记忆
        candidates: list[MemoryItem] = []

        if memory_types is None or "semantic" in memory_types:
            candidates.extend(self.semantic.list_all())
        if memory_types is None or "episodic" in memory_types:
            candidates.extend(self.episodic.list_all())
        if memory_types is None or "procedural" in memory_types:
            candidates.extend(self.procedural.list_all())
        if memory_types is None or "working" in memory_types:
            candidates.extend(self.working.list_all())

        # 执行混合检索
        results = self.retriever.search(
            candidates, query,
            top_k=top_k,
            threshold=threshold,
        )

        # 追踪引用
        for r in results:
            self._track_reference(r.memory.id, query)

        return results

    def search_semantic_only(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """仅搜索语义记忆。"""
        return self.search(query, memory_types=["semantic"], top_k=top_k)

    def search_episodic_only(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """仅搜索情景记忆。"""
        return self.search(query, memory_types=["episodic"], top_k=top_k)

    def search_procedural_only(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """仅搜索程序记忆。"""
        return self.search(query, memory_types=["procedural"], top_k=top_k)

    # ==================== 更新和合并 ====================

    def update_memory(self, memory_type: str, memory_id: str, **kwargs) -> Optional[MemoryItem]:
        """更新记忆。"""
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return None
        return memory_store.update(memory_id, **kwargs)

    def delete_memory(self, memory_type: str, memory_id: str) -> bool:
        """删除记忆。"""
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return False
        return memory_store.delete(memory_id)

    def get_memory(self, memory_type: str, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆。"""
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return None
        return memory_store.get(memory_id)

    # ==================== 整合操作 ====================

    def consolidate_memories(self, memory_type: str = "semantic", topic: Optional[str] = None) -> list[MemoryItem]:
        """
        整合指定类型的记忆。

        Args:
            memory_type: 记忆类型
            topic: 可选的主题

        Returns:
            整合后的新记忆列表
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return []

        memories = memory_store.list_all()
        groups = self.consolidator.find_consolidatable(memories)

        consolidated = []
        for group in groups:
            new_memory = self.consolidator.consolidate(group, topic)
            if new_memory:
                # 删除原始记忆，添加整合后的记忆
                for m in group:
                    memory_store.delete(m.id)
                item = memory_store.add(
                    content=new_memory.content,
                    importance=new_memory.importance,
                    metadata=new_memory.metadata,
                )
                # 自动冲突检查（整合后的记忆也可能与现有记忆冲突）
                self._auto_conflict_check(item)
                consolidated.append(item)

        return consolidated

    # ==================== 冲突检测（R2.3 缺口补全） ====================

    def detect_conflicts(self, memory_type: str = "semantic") -> list[tuple]:
        """
        检测指定类型记忆中的冲突。

        Args:
            memory_type: 记忆类型（默认 semantic）

        Returns:
            冲突记忆对列表
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return []
        memories = memory_store.list_all()
        return self.conflict_detector.find_conflicts(memories)

    def resolve_conflicts(self, memory_type: str = "semantic") -> list[dict]:
        """
        解决指定类型记忆中的冲突（保留重要性更高者）。

        Args:
            memory_type: 记忆类型（默认 semantic）

        Returns:
            冲突解决记录列表
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return []
        memories = memory_store.list_all()
        conflicts = self.conflict_detector.find_conflicts(memories)
        resolved = []
        for m1, m2 in conflicts:
            keep = self.conflict_detector.resolve_conflict(m1, m2)
            discard = m2 if keep.id == m1.id else m1
            memory_store.delete(discard.id)
            resolved.append({
                "keep_id": keep.id,
                "discard_id": discard.id,
                "keep_content": keep.content,
                "discard_content": discard.content,
            })
        return resolved

    # ==================== 关联遗忘（R2.3 缺口补全） ====================

    def forget_with_associates(
        self,
        memory_type: str,
        memory_id: str,
        associates: list[str],
    ) -> dict:
        """
        遗忘一条记忆并处理其关联记忆。

        策略：
        - 关联记忆重要性 ≥ 阈值：断联保留（重要性降低）
        - 关联记忆重要性 < 阈值：级联遗忘（一起删除）

        Args:
            memory_type: 记忆类型
            memory_id: 被遗忘的记忆 ID
            associates: 关联记忆 ID 列表

        Returns:
            处置结果（cascade_ids / disconnected_ids）
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return {"cascade_ids": [], "disconnected_ids": []}

        # 获取被遗忘记忆
        forgotten = memory_store.get(memory_id)
        if not forgotten:
            return {"cascade_ids": [], "disconnected_ids": []}

        # 获取关联记忆
        assoc_items = []
        for aid in associates:
            item = memory_store.get(aid)
            if item:
                assoc_items.append(item)

        # 处理关联
        cascade, disconnected = self.associated_forgetter.forget_with_associates(
            forgotten, assoc_items
        )

        # 执行：删除被遗忘 + 级联，更新断联
        memory_store.delete(memory_id)
        cascade_ids = []
        for c in cascade:
            memory_store.delete(c.id)
            cascade_ids.append(c.id)

        disconnected_ids = []
        for d in disconnected:
            memory_store.update(d.id, importance=d.importance)
            disconnected_ids.append(d.id)

        return {
            "forgotten_id": memory_id,
            "cascade_ids": cascade_ids,
            "disconnected_ids": disconnected_ids,
        }

    # ==================== 遗忘操作 ====================

    def forget(self, memory_type: Optional[str] = None) -> dict[str, list[str]]:
        """
        执行遗忘流程。

        Args:
            memory_type: 指定记忆类型（None 表示全部）

        Returns:
            各类型被遗忘的记忆 ID
        """
        result = {}
        types_to_forget = [memory_type] if memory_type else ["semantic", "episodic", "procedural"]

        for mtype in types_to_forget:
            memory_store = self._get_memory_store(mtype)
            if not memory_store:
                continue

            memories = memory_store.list_all()
            forgotten_ids, retained = self.forgetter.forget(memories)

            # 删除被遗忘的记忆，并对其关联记忆执行处置（级联/断联）
            for fid in forgotten_ids:
                # 找出关联记忆（同类型，排除被遗忘者）
                associates = [
                    m.id for m in memories
                    if m.id != fid and m.id not in forgotten_ids
                ]
                if associates:
                    self.forget_with_associates(mtype, fid, associates)
                else:
                    memory_store.delete(fid)

            result[mtype] = forgotten_ids

        return result

    def get_stats(self) -> dict:
        """获取记忆系统统计信息。"""
        return {
            "semantic_count": self.semantic.count(),
            "episodic_count": self.episodic.count(),
            "procedural_count": self.procedural.count(),
            "working_count": self.working.count(),
            "total_long_term": self.semantic.count() + self.episodic.count() + self.procedural.count(),
            "reference_tracker_size": len(self._reference_tracker),
        }

    def clear_all(self) -> None:
        """清空所有记忆。"""
        self.semantic.clear()
        self.episodic.clear()
        self.procedural.clear()
        self.working.clear()
        self._reference_tracker.clear()

    # ==================== 内部方法 ====================

    def detect_stale_procedural(self) -> list[MemoryItem]:
        """
        检测陈化的程序记忆（技能失效）。

        陈化 ≠ 变旧：陈化是技能随环境变化而失效（失败过多/长期未用且低重要性/
        近期失败级联），非纯时间衰减。供上层决定降级或淘汰。

        Returns:
            陈化的程序记忆列表
        """
        items = self.procedural.list_all()
        return self.staleness_detector.find_stale(items)

    def calibrate_importance(self, memory_type: str, memory_id: str) -> Optional[float]:
        """
        校准单条记忆的重要性（从使用反馈动态校准）。

        校准后的重要性直接用于遗忘器的保留分数计算，实现「重要性 ↔ 遗忘」联动。
        校准结果写回记忆的 importance 字段。

        Args:
            memory_type: 记忆类型（semantic/episodic/procedural）
            memory_id: 记忆 id

        Returns:
            校准后的重要性，或 None（记忆不存在）
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return None
        item = memory_store.get(memory_id)
        if not item:
            return None
        calibrated = self.importance_calibrator.calibrate(item)
        # 写回校准后的重要性
        memory_store.update(memory_id, importance=calibrated)
        return calibrated

    def calibrate_all_importance(self, memory_type: str) -> dict[str, float]:
        """
        校准某类型全部记忆的重要性。

        Args:
            memory_type: 记忆类型

        Returns:
            {memory_id: calibrated_importance}
        """
        memory_store = self._get_memory_store(memory_type)
        if not memory_store:
            return {}
        results = {}
        for item in memory_store.list_all():
            cal = self.importance_calibrator.calibrate(item)
            memory_store.update(item.id, importance=cal)
            results[item.id] = cal
        return results

    def _get_memory_store(self, memory_type: str):
        """根据类型获取记忆存储。"""
        stores = {
            "semantic": self.semantic,
            "episodic": self.episodic,
            "procedural": self.procedural,
            "working": self.working,
        }
        return stores.get(memory_type)

    def _auto_conflict_check(self, item: MemoryItem) -> list[dict]:
        """
        自动冲突检查（添加新记忆后调用）。

        检测新记忆与同类型现有记忆的冲突，冲突时标记 metadata
        （conflict_candidate + conflict_with），而非立即删除——保留信息供上层决策。

        Args:
            item: 刚添加的记忆项

        Returns:
            冲突标记记录列表
        """
        memory_store = self._get_memory_store(item.memory_type)
        if not memory_store:
            return []

        # 收集全部记忆（现有 + 新），找涉及新记忆的冲突对
        all_memories = memory_store.list_all()
        conflicts = self.conflict_detector.find_conflicts(all_memories)

        marks = []
        for m1, m2 in conflicts:
            if m1.id != item.id and m2.id != item.id:
                continue  # 不涉及新记忆，跳过
            other = m2 if m1.id == item.id else m1
            # 标记新记忆的元数据
            meta = dict(item.metadata or {})
            meta["conflict_candidate"] = True
            meta["conflict_with"] = other.id
            memory_store.update(item.id, metadata=meta)
            marks.append({
                "memory_id": item.id,
                "conflict_with": other.id,
                "other_content": other.content,
            })
        return marks

    def _track_reference(self, memory_id: str, query: str) -> None:
        """追踪记忆引用。"""
        if memory_id not in self._reference_tracker:
            self._reference_tracker[memory_id] = []
        self._reference_tracker[memory_id].append({
            "query": query,
            "timestamp": time.time(),
        })

    def get_reference_history(self, memory_id: str) -> list[dict]:
        """获取记忆的引用历史。"""
        return self._reference_tracker.get(memory_id, [])