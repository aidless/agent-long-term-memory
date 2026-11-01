"""
简单向量存储 - 基于内存的向量存储实现，支持 JSON 持久化。
使用 TF-IDF + 余弦相似度进行语义匹配，无需外部嵌入模型。
"""

import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class VectorRecord:
    """向量存储中的单条记录。"""

    id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "vector": self.vector,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VectorRecord":
        return cls(
            id=data["id"],
            text=data["text"],
            vector=data["vector"],
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
        )


class SimpleVectorStore:
    """
    基于内存的简单向量存储。

    使用词袋模型 (Bag of Words) + TF-IDF 权重将文本转换为向量，
    通过余弦相似度进行检索。支持 JSON 文件持久化。
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._records: dict[str, VectorRecord] = {}
        self._vocabulary: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._doc_freq: dict[str, int] = {}
        self._total_docs: int = 0
        self.persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            self._load()

    def _tokenize(self, text: str) -> list[str]:
        """简单的中英文分词。"""
        # 英文分词
        en_tokens = re.findall(r"[a-zA-Z]+", text.lower())
        # 中文单字分词（简化版，实际可用 jieba）
        zh_tokens = list(re.findall(r"[\u4e00-\u9fff]", text))
        return en_tokens + zh_tokens

    def _update_vocabulary(self, tokens: list[str]) -> None:
        """更新词汇表和文档频率。"""
        for token in set(tokens):
            if token not in self._vocabulary:
                self._vocabulary[token] = len(self._vocabulary)
                self._doc_freq[token] = 0
            self._doc_freq[token] += 1
        self._total_docs += 1
        self._update_idf()

    def _update_idf(self) -> None:
        """更新 IDF 权重。"""
        for token, freq in self._doc_freq.items():
            self._idf[token] = math.log((self._total_docs + 1) / (freq + 1)) + 1

    def _text_to_vector(self, text: str) -> list[float]:
        """将文本转换为 TF-IDF 向量。"""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        vocab_size = len(self._vocabulary)

        if vocab_size == 0:
            return [0.0] * 100  # 默认维度

        vec = np.zeros(vocab_size)
        for token, count in tf.items():
            if token in self._vocabulary:
                idx = self._vocabulary[token]
                tf_val = count / len(tokens) if tokens else 0
                idf_val = self._idf.get(token, 1.0)
                vec[idx] = tf_val * idf_val

        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        return vec.tolist()

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """计算两个向量的余弦相似度。"""
        a = np.array(vec_a)
        b = np.array(vec_b)
        if len(a) != len(b):
            # 维度不同时，截断到较小维度
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def add(
        self,
        text: str,
        record_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        importance: float = 0.5,
    ) -> VectorRecord:
        """添加一条记录到向量存储。"""
        if record_id is None:
            record_id = f"mem_{int(time.time() * 1000)}_{len(self._records)}"

        # 先更新词汇表再生成向量
        tokens = self._tokenize(text)
        self._update_vocabulary(tokens)

        # 重新生成所有已有记录的向量（因为 IDF 变了）
        for rid, rec in self._records.items():
            rec.vector = self._text_to_vector(rec.text)

        vector = self._text_to_vector(text)

        record = VectorRecord(
            id=record_id,
            text=text,
            vector=vector,
            metadata=metadata or {},
            importance=importance,
        )
        self._records[record_id] = record

        if self.persist_path:
            self._save()

        return record

    def get(self, record_id: str) -> Optional[VectorRecord]:
        """根据 ID 获取记录。"""
        record = self._records.get(record_id)
        if record:
            record.access_count += 1
        return record

    def update(self, record_id: str, text: Optional[str] = None, metadata: Optional[dict] = None, importance: Optional[float] = None) -> Optional[VectorRecord]:
        """更新一条记录。"""
        record = self._records.get(record_id)
        if not record:
            return None

        if text is not None:
            record.text = text
            record.vector = self._text_to_vector(text)
        if metadata is not None:
            record.metadata.update(metadata)
        if importance is not None:
            record.importance = importance
        record.updated_at = time.time()

        if self.persist_path:
            self._save()
        return record

    def delete(self, record_id: str) -> bool:
        """删除一条记录。"""
        if record_id in self._records:
            del self._records[record_id]
            if self.persist_path:
                self._save()
            return True
        return False

    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.0,
        filter_metadata: Optional[dict] = None,
    ) -> list[tuple[VectorRecord, float]]:
        """
        语义搜索。

        Args:
            query: 查询文本
            top_k: 返回前 k 条结果
            threshold: 相似度阈值
            filter_metadata: 元数据过滤条件

        Returns:
            (记录, 相似度分数) 列表，按相似度降序排列
        """
        query_vector = self._text_to_vector(query)

        results: list[tuple[VectorRecord, float]] = []
        for record in self._records.values():
            # 元数据过滤
            if filter_metadata:
                match = True
                for key, value in filter_metadata.items():
                    if record.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            sim = self._cosine_similarity(query_vector, record.vector)
            if sim >= threshold:
                record.access_count += 1
                results.append((record, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def list_all(self) -> list[VectorRecord]:
        """列出所有记录。"""
        return list(self._records.values())

    def count(self) -> int:
        """返回记录数量。"""
        return len(self._records)

    def clear(self) -> None:
        """清空所有记录。"""
        self._records.clear()
        self._vocabulary.clear()
        self._idf.clear()
        self._doc_freq.clear()
        self._total_docs = 0
        if self.persist_path and os.path.exists(self.persist_path):
            os.remove(self.persist_path)

    def _save(self) -> None:
        """持久化到 JSON 文件。"""
        if not self.persist_path:
            return
        data = {
            "records": {rid: rec.to_dict() for rid, rec in self._records.items()},
            "vocabulary": self._vocabulary,
            "idf": self._idf,
            "doc_freq": self._doc_freq,
            "total_docs": self._total_docs,
        }
        os.makedirs(os.path.dirname(self.persist_path) if os.path.dirname(self.persist_path) else ".", exist_ok=True)
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从 JSON 文件加载。"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        with open(self.persist_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._vocabulary = data.get("vocabulary", {})
        self._idf = data.get("idf", {})
        self._doc_freq = data.get("doc_freq", {})
        self._total_docs = data.get("total_docs", 0)
        self._records = {
            rid: VectorRecord.from_dict(rd)
            for rid, rd in data.get("records", {}).items()
        }