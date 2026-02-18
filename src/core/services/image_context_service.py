"""图片上下文构建服务。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union

from src.core.domain import PersonaConfig


logger = logging.getLogger(__name__)


class ImageContextService:
    """从最近消息中提取图片信息，生成可注入回复的上下文摘要。"""

    def __init__(
        self,
        *,
        config: Union[PersonaConfig, Dict[str, Any]],
        image_resolver: Any,
        image_understander: Any,
        message_repo: Any,
    ) -> None:
        self.config = config
        self.image_resolver = image_resolver
        self.image_understander = image_understander
        self.message_repo = message_repo

    def _image_cfg_dict(self) -> Dict[str, Any]:
        if isinstance(self.config, PersonaConfig):
            cfg = self.config.image_understanding
            return {
                "enabled": cfg.enabled,
                "max_images_per_round": cfg.max_images_per_round,
                "analyze_window_size": cfg.analyze_window_size,
                "cache_enabled": cfg.cache_enabled,
            }
        raw = self.config.get("image_understanding", {})
        return raw if isinstance(raw, dict) else {}

    def _max_images_per_round(self) -> int:
        value = self._image_cfg_dict().get("max_images_per_round", 5)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 5

    def _analyze_window_size(self) -> int:
        value = self._image_cfg_dict().get("analyze_window_size", 20)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 20

    def _cache_enabled(self) -> bool:
        return bool(self._image_cfg_dict().get("cache_enabled", True))

    async def build_context(self, conv_id: str, recent_messages: List[Dict[str, Any]]) -> str:
        """生成图片上下文摘要文本。"""
        zero_fetch_stats = {"url": 0, "file_id": 0}
        if not recent_messages:
            self._log_build_metrics(
                conv_id,
                images=0,
                image_cache_hit=0,
                analyzed=0,
                image_understanding_cost=0,
                fetch_source_count=zero_fetch_stats,
            )
            return ""

        candidates = self._collect_candidates(recent_messages)
        if not candidates:
            self._log_build_metrics(
                conv_id,
                images=0,
                image_cache_hit=0,
                analyzed=0,
                image_understanding_cost=0,
                fetch_source_count=zero_fetch_stats,
            )
            return ""

        # 只看最近 N 张图片，避免上下文过长
        max_images = self._max_images_per_round()
        candidates = candidates[:max_images]

        cache_enabled = self._cache_enabled()
        summary_slots: List[str] = ["" for _ in candidates]
        cache_hit = 0
        pending_for_understanding: List[Tuple[int, Dict[str, Any], Dict[str, Any], str]] = []
        pending_metadata_updates: Dict[int, Dict[str, Any]] = {}
        fetch_source_count = {"url": 0, "file_id": 0}
        image_understanding_cost = 0

        for index, entry in enumerate(candidates):
            cached_summary = self._read_cached_summary(entry["image"]) if cache_enabled else ""
            if cached_summary:
                summary_slots[index] = cached_summary
                cache_hit += 1
                continue

            resolved = await self.image_resolver.resolve(
                conv_id=conv_id,
                message_id=entry["message_id"],
                image_meta=entry["image"],
            )
            if not resolved:
                if cache_enabled:
                    self._write_understanding(
                        entry["image"],
                        summary="",
                        fetch_source="",
                        error="resolve_failed",
                    )
                    self._mark_pending_metadata(entry, pending_metadata_updates)
                continue

            source = str(getattr(resolved, "source", "") or "")
            if source in fetch_source_count:
                fetch_source_count[source] += 1

            payload = {
                "image_bytes": getattr(resolved, "image_bytes", b""),
                "mime": getattr(resolved, "mime", "image/jpeg"),
                "url": getattr(resolved, "original_url", ""),
            }
            pending_for_understanding.append((index, entry, payload, source))

        if pending_for_understanding:
            image_understanding_cost = len(pending_for_understanding)
            payloads = [item[2] for item in pending_for_understanding]
            usage_contexts = [
                {
                    "plugin_name": "persona",
                    "module_name": "image_understanding",
                    "operation": "image_understanding",
                    "conv_id": conv_id,
                    "message_id": item[1].get("message_id"),
                }
                for item in pending_for_understanding
            ]
            summaries = await self.image_understander.summarize_images(
                payloads,
                usage_contexts=usage_contexts,
            )
            if len(summaries) < len(pending_for_understanding):
                summaries.extend([""] * (len(pending_for_understanding) - len(summaries)))

            for (index, entry, _, source), summary in zip(pending_for_understanding, summaries):
                text = str(summary or "").strip()
                if text:
                    summary_slots[index] = text
                    if cache_enabled:
                        self._write_understanding(
                            entry["image"],
                            summary=text,
                            fetch_source=source,
                            error="",
                        )
                        self._mark_pending_metadata(entry, pending_metadata_updates)
                elif cache_enabled:
                    logger.warning(
                        "图片理解返回空摘要: conv_id=%s message_id=%s fetch_source=%s",
                        conv_id,
                        entry.get("message_id"),
                        source or "unknown",
                    )
                    self._write_understanding(
                        entry["image"],
                        summary="",
                        fetch_source=source,
                        error="understand_failed",
                    )
                    self._mark_pending_metadata(entry, pending_metadata_updates)

        metadata_updated_count = 0
        if pending_metadata_updates:
            for message_id, metadata in pending_metadata_updates.items():
                ok = await self.message_repo.update_message_metadata(message_id, metadata)
                if not ok:
                    logger.warning("图片缓存 metadata 回写失败: conv_id=%s message_id=%s", conv_id, message_id)
                else:
                    metadata_updated_count += 1
            logger.info(
                "图片理解 metadata 回写完成: conv_id=%s message_updated=%s",
                conv_id,
                metadata_updated_count,
            )

        lines = []
        for entry, summary in zip(candidates, summary_slots):
            if not summary:
                continue
            user_name = str(entry["message"].get("user_name") or "用户")
            lines.append(f"- {user_name} 发图：{summary}")

        self._log_build_metrics(
            conv_id,
            images=len(candidates),
            image_cache_hit=cache_hit,
            analyzed=len(pending_for_understanding),
            image_understanding_cost=image_understanding_cost,
            fetch_source_count=fetch_source_count,
        )

        if not lines:
            return ""
        return "【图片上下文】\n" + "\n".join(lines)

    @staticmethod
    def _log_build_metrics(
        conv_id: str,
        *,
        images: int,
        image_cache_hit: int,
        analyzed: int,
        image_understanding_cost: int,
        fetch_source_count: Dict[str, int],
    ) -> None:
        logger.info(
            "图片上下文构建完成: conv_id=%s images=%s image_cache_hit=%s analyzed=%s "
            "image_understanding_cost=%s image_fetch_source(url)=%s image_fetch_source(file_id)=%s",
            conv_id,
            images,
            image_cache_hit,
            analyzed,
            image_understanding_cost,
            fetch_source_count.get("url", 0),
            fetch_source_count.get("file_id", 0),
        )

    def _collect_candidates(self, recent_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        window_size = self._analyze_window_size()
        window = recent_messages[-window_size:]

        candidates: List[Dict[str, Any]] = []
        for message in reversed(window):
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            media = metadata.get("media")
            if not isinstance(media, dict):
                continue
            images = media.get("images")
            if not isinstance(images, list):
                continue

            for image in reversed(images):
                if not isinstance(image, dict):
                    continue
                candidates.append(
                    {
                        "message": message,
                        "message_id": message.get("id"),
                        "metadata": metadata,
                        "image": image,
                    }
                )
        return candidates

    @staticmethod
    def _read_cached_summary(image_meta: Dict[str, Any]) -> str:
        data = image_meta.get("understanding")
        if not isinstance(data, dict):
            return ""
        return str(data.get("summary") or "").strip()

    @staticmethod
    def _write_understanding(
        image_meta: Dict[str, Any],
        *,
        summary: str,
        fetch_source: str,
        error: str,
    ) -> None:
        payload = {
            "summary": summary,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if fetch_source:
            payload["fetch_source"] = fetch_source
        if error:
            payload["error"] = error
        image_meta["understanding"] = payload

    @staticmethod
    def _mark_pending_metadata(
        entry: Dict[str, Any],
        pending_metadata_updates: Dict[int, Dict[str, Any]],
    ) -> None:
        message_id = entry.get("message_id")
        metadata = entry.get("metadata")
        if not isinstance(message_id, int):
            return
        if not isinstance(metadata, dict):
            return
        pending_metadata_updates[message_id] = metadata
