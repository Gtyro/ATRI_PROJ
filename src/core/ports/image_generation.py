"""Image generation capabilities supplied to an individual reply."""

from typing import Awaitable, Callable, Protocol


class ImageGeneratorPort(Protocol):
    async def generate(self, prompt: str, *, use_character_reference: bool = False) -> bytes:
        ...


ImageGenerationCallback = Callable[[str, bool], Awaitable[dict[str, str]]]
