import asyncio

from src.core.services.memory_service import MemoryService


class _RepoStub:
    def __init__(self):
        self.reinforce_calls = []

    async def reinforce_memories(self, memory_ids, *, boost, max_weight):
        self.reinforce_calls.append({
            "memory_ids": list(memory_ids),
            "boost": boost,
            "max_weight": max_weight,
        })
        return len(memory_ids)


class _RetrieverStub:
    def __init__(self, results_by_keyword):
        self.results_by_keyword = results_by_keyword

    async def search_for_memories(self, query, user_id=None, limit=5, conv_id=None):
        return list(self.results_by_keyword.get(query, []))


def test_retrieve_memory_payload_dedupes_candidates_and_orders_by_weight():
    retriever = _RetrieverStub(
        {
            "张三": [
                {
                    "id": "mem-1",
                    "title": "张三近况",
                    "content": "张三最近在做项目A",
                    "weight": 1.2,
                    "last_accessed": 200.0,
                    "created_at": 100.0,
                    "source": "topic",
                }
            ],
            "项目A": [
                {
                    "id": "mem-1",
                    "title": "张三近况",
                    "content": "张三最近在做项目A",
                    "weight": 1.2,
                    "last_accessed": 200.0,
                    "created_at": 100.0,
                    "source": "node",
                },
                {
                    "id": "mem-2",
                    "title": "项目A状态",
                    "content": "项目A延期到下周",
                    "weight": 0.8,
                    "last_accessed": 150.0,
                    "created_at": 120.0,
                    "source": "topic",
                },
            ],
        }
    )
    service = MemoryService(_RepoStub(), retriever)

    payload = asyncio.run(
        service.retrieve_memory_payload("张三 项目A", user_id=None, conv_id="group_1")
    )

    assert [candidate["id"] for candidate in payload["candidates"]] == ["mem-1", "mem-2"]
    assert "【张三近况】张三最近在做项目A" in payload["memory_context"]
    assert payload["selection_applied"] is False


def test_retrieve_memory_payload_reinforces_selected_memories_only():
    repo = _RepoStub()
    retriever = _RetrieverStub(
        {
            "张三": [
                {
                    "id": "mem-1",
                    "title": "张三近况",
                    "content": "张三最近在做项目A",
                    "weight": 1.2,
                    "last_accessed": 200.0,
                    "created_at": 100.0,
                    "source": "topic",
                },
                {
                    "id": "mem-2",
                    "title": "项目A状态",
                    "content": "项目A延期到下周",
                    "weight": 0.8,
                    "last_accessed": 150.0,
                    "created_at": 120.0,
                    "source": "topic",
                },
            ]
        }
    )
    service = MemoryService(repo, retriever)

    payload = asyncio.run(
        service.retrieve_memory_payload(
            "张三",
            user_id=None,
            conv_id="group_1",
            selected_ids=["mem-2"],
            reinforce_selected=True,
        )
    )

    assert payload["selection_applied"] is True
    assert payload["selected_ids"] == ["mem-2"]
    assert "【项目A状态】项目A延期到下周" in payload["memory_context"]
    assert repo.reinforce_calls == [
        {
            "memory_ids": ["mem-2"],
            "boost": MemoryService.DEFAULT_RECALL_BOOST,
            "max_weight": MemoryService.DEFAULT_MAX_WEIGHT,
        }
    ]
