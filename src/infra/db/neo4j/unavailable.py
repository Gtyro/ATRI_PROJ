"""Neo4j 不可用时的降级实现。"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


class Neo4jUnavailableError(RuntimeError):
    """Neo4j 当前不可用。"""


class UnavailableMemoryRepository:
    """当 Neo4j 不可用时，提供最小可运行的仓库占位实现。"""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "").strip() or "Neo4j 当前不可用"

    def is_available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self.reason

    def _raise_unavailable(self) -> None:
        raise Neo4jUnavailableError(self.reason)

    async def run_cypher(self, query: str, params: Dict | None = None) -> Tuple[List[Any], Dict[str, Any]]:
        self._raise_unavailable()

    async def update_or_create_node(self, conv_id: str, node_name: str, is_permanent: bool = False) -> Any:
        self._raise_unavailable()

    async def store_memory(self, conv_id: str, memory_data: Dict[str, Any]) -> Any:
        self._raise_unavailable()

    async def _link_nodes_to_memory(self, memory: Any, node_ids: Sequence[str]) -> None:
        self._raise_unavailable()

    async def store_association(self, node_id_a: str, node_id_b: str) -> None:
        self._raise_unavailable()

    async def reinforce_memories(
        self,
        memory_ids: Sequence[str],
        *,
        boost: float,
        max_weight: float,
    ) -> int:
        return 0

    async def delete_memories_by_time_range(
        self,
        conv_id: str,
        start_time: Any,
        end_time: Any,
    ) -> int:
        return 0

    async def get_nodes(self) -> List[Any]:
        return []

    async def apply_decay(self, node_id: str, decay_rate: float) -> bool:
        return False

    async def apply_association_decay(self, decay_rate: float) -> int:
        return 0

    async def apply_memory_decay(self, decay_rate: float) -> int:
        return 0

    async def clean_old_memories_by_conv(self, conv_id: str, max_memories: int = 500) -> int:
        return 0

    async def get_nodes_by_conv_id(
        self,
        conv_id: str,
        order_by: str = "-act_lv",
        limit: int | None = None,
        is_permanent: bool | None = None,
    ) -> List[Any]:
        return []

    async def delete_node(self, node_id: str) -> bool:
        return False


def is_memory_repo_available(repo: Any) -> bool:
    checker = getattr(repo, "is_available", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return False
    return repo is not None


def get_memory_repo_unavailable_reason(repo: Any) -> str:
    getter = getattr(repo, "unavailable_reason", None)
    if callable(getter):
        try:
            return str(getter() or "").strip()
        except Exception:
            return ""
    return ""
