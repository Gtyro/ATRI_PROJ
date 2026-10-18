"""Keep generated attachments local to one reply, including provider fallback."""

import asyncio
import logging

from src.core.domain.image_generation_error import ImageGenerationError
from src.core.ports.image_generation import ImageGeneratorPort


class ImageGenerationTurn:
    """Execute at most one paid generation per reply and retain its outcome."""

    def __init__(self, generator: ImageGeneratorPort, conv_id: str) -> None:
        self.generator = generator
        self.conv_id = conv_id
        self.images: list[bytes] = []
        self.result: dict[str, str] | None = None
        self._lock = asyncio.Lock()

    async def generate(
        self,
        prompt: str,
        use_character_reference: bool = False,
    ) -> dict[str, str]:
        async with self._lock:
            if self.result is not None:
                return dict(self.result)
            logging.info("Persona image generation started: conv_id=%s", self.conv_id)
            try:
                if use_character_reference:
                    image = await self.generator.generate(
                        prompt,
                        use_character_reference=True,
                    )
                else:
                    image = await self.generator.generate(prompt)
                if not isinstance(image, bytes) or not image:
                    raise ImageGenerationError("Image generator returned no image bytes", code="no_image")
            except Exception as exc:
                error = exc if isinstance(exc, ImageGenerationError) else ImageGenerationError(
                    "图像生成发生内部异常", code="internal_error", detail=type(exc).__name__,
                )
                logging.warning(
                    "Persona image generation failed: conv_id=%s error=%s %s",
                    self.conv_id,
                    type(exc).__name__,
                    error.diagnostic_summary(),
                )
                self.result = {
                    "status": "error",
                    "error_code": error.code,
                    "message": error.user_message,
                }
            else:
                self.images.append(image)
                self.result = {
                    "status": "ok",
                    "message": "Image generated. It will be attached to this reply automatically.",
                }
                logging.info(
                    "Persona image generation completed: conv_id=%s bytes=%s",
                    self.conv_id,
                    len(image),
                )
            return dict(self.result)
