import asyncio

from src.infra.memory.decay_manager import DecayManager


class _GroupConfigStub:
    def __init__(self, group_ids):
        self.group_ids = list(group_ids)

    async def get_distinct_group_ids(self, plugin_name: str):
        assert plugin_name == "persona"
        return list(self.group_ids)


class _MemoryRepoStub:
    def __init__(self):
        self.cleaned_conv_ids = []

    async def clean_old_memories_by_conv(self, conv_id: str, max_memories: int = 500):
        self.cleaned_conv_ids.append((conv_id, max_memories))
        return 1


def test_cleanup_old_nodes_normalizes_group_ids_to_conv_ids():
    manager = DecayManager(
        memory_repo=object(),
        group_config=_GroupConfigStub(["42", "group_99"]),
        plugin_name="persona",
    )
    captured_conv_ids = []

    async def fake_forget_node_by_conv(conv_id: str) -> int:
        captured_conv_ids.append(conv_id)
        return 1

    manager.forget_node_by_conv = fake_forget_node_by_conv

    cleaned = asyncio.run(manager.cleanup_old_nodes())

    assert cleaned == 2
    assert captured_conv_ids == ["group_42", "group_99"]


def test_cleanup_old_memories_normalizes_group_ids_to_conv_ids():
    memory_repo = _MemoryRepoStub()
    manager = DecayManager(
        memory_repo=memory_repo,
        group_config=_GroupConfigStub(["42", "group_99"]),
        plugin_name="persona",
        max_memories_per_conv=321,
    )

    cleaned = asyncio.run(manager.cleanup_old_memories())

    assert cleaned == 2
    assert memory_repo.cleaned_conv_ids == [
        ("group_42", 321),
        ("group_99", 321),
    ]
