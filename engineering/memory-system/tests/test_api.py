"""
测试 API 接口。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _setup_api_managers():
    """确保 API 的 manager 被初始化。"""
    from app.api.memory import set_manager as set_memory_manager
    from app.api.search import set_manager as set_search_manager
    from app.api.agent import set_manager as set_agent_manager
    from manager.memory_manager import MemoryManager

    manager = MemoryManager()
    set_memory_manager(manager)
    set_search_manager(manager)
    set_agent_manager(manager)


@pytest.fixture
def client():
    return TestClient(app)


class TestMemoryAPI:
    """记忆 CRUD API 测试。"""

    def test_add_semantic_memory(self, client):
        """测试添加语义记忆。"""
        resp = client.post("/api/memory/", json={
            "content": "Python 是一种编程语言",
            "memory_type": "semantic",
            "importance": 0.8,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Python 是一种编程语言"
        assert data["memory_type"] == "semantic"
        assert data["importance"] == 0.8

    def test_add_episodic_memory(self, client):
        """测试添加情景记忆。"""
        resp = client.post("/api/memory/", json={
            "content": "用户询问了天气",
            "memory_type": "episodic",
            "emotion": "neutral",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["memory_type"] == "episodic"

    def test_get_memory(self, client):
        """测试获取记忆。"""
        # 先添加
        add_resp = client.post("/api/memory/", json={
            "content": "测试获取",
            "memory_type": "semantic",
        })
        mem_id = add_resp.json()["id"]

        # 再获取
        get_resp = client.get(f"/api/memory/semantic/{mem_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == "测试获取"

    def test_get_nonexistent_memory(self, client):
        """测试获取不存在的记忆。"""
        resp = client.get("/api/memory/semantic/nonexistent_id")
        assert resp.status_code == 404

    def test_update_memory(self, client):
        """测试更新记忆。"""
        add_resp = client.post("/api/memory/", json={
            "content": "原始内容",
            "memory_type": "semantic",
        })
        mem_id = add_resp.json()["id"]

        update_resp = client.put(f"/api/memory/semantic/{mem_id}", json={
            "content": "更新后的内容",
            "importance": 0.9,
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["content"] == "更新后的内容"
        assert update_resp.json()["importance"] == 0.9

    def test_delete_memory(self, client):
        """测试删除记忆。"""
        add_resp = client.post("/api/memory/", json={
            "content": "待删除",
            "memory_type": "semantic",
        })
        mem_id = add_resp.json()["id"]

        del_resp = client.delete(f"/api/memory/semantic/{mem_id}")
        assert del_resp.status_code == 200

    def test_get_stats(self, client):
        """测试获取统计信息。"""
        resp = client.get("/api/memory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "semantic_count" in data
        assert "total_long_term" in data


class TestSearchAPI:
    """检索 API 测试。"""

    def test_search_memories(self, client):
        """测试搜索记忆。"""
        # 先添加一些记忆
        client.post("/api/memory/", json={"content": "Python 编程语言", "memory_type": "semantic"})
        client.post("/api/memory/", json={"content": "Java 编程语言", "memory_type": "semantic"})

        resp = client.post("/api/search/", json={
            "query": "Python",
            "top_k": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "Python"
        assert "results" in data

    def test_extract_memories(self, client):
        """测试记忆提取。"""
        resp = client.post("/api/search/extract", json={
            "text": "我叫张三，我喜欢编程。",
            "speaker": "user",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["memories"]) >= 1
        assert len(data["entities"]) >= 1


class TestAgentAPI:
    """Agent 集成 API 测试。"""

    def test_build_prompt(self, client):
        """测试构建 Prompt。"""
        # 添加一些记忆
        client.post("/api/memory/", json={"content": "用户喜欢编程", "memory_type": "semantic"})

        resp = client.post("/api/agent/build-prompt", json={
            "system_prompt": "你是一个AI助手",
            "user_message": "帮我写一个Python程序",
            "query": "编程 Python",
            "top_k": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt" in data
        assert "你是一个AI助手" in data["prompt"]
        assert "帮我写一个Python程序" in data["prompt"]
        assert data["memory_count"] >= 0
        assert data["estimated_tokens"] > 0

    def test_context_window_allocation(self, client):
        """测试上下文窗口分配。"""
        resp = client.get("/api/agent/context-window/allocation", params={"max_tokens": 4096})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4096
        assert data["system_prompt"] > 0
        assert data["memory"] > 0

    def test_working_memory_crud(self, client):
        """测试工作记忆增删查。"""
        # 添加
        resp = client.post("/api/agent/working-memory", params={"text": "临时上下文", "speaker": "user"})
        assert resp.status_code == 200

        # 获取
        resp = client.get("/api/agent/working-memory")
        assert resp.status_code == 200

        # 清空
        resp = client.delete("/api/agent/working-memory")
        assert resp.status_code == 200

    def test_health_check(self, client):
        """测试健康检查。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root(self, client):
        """测试根路由。"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Agent Long-Term Memory System"