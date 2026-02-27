"""图片上下文构建服务。"""

from __future__ import annotations

import inspect
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union

from src.core.domain import PersonaConfig


logger = logging.getLogger(__name__)
KNOWN_RESOLVED_VIAS = (
    "url",
    "get_image",
    "get_file_by_file_id",
    "get_file_by_file",
    "file_id_local_path",
    "failed",
)
KNOWN_ERROR_CATEGORIES = (
    "4xx",
    "5xx",
    "timeout",
    "network",
    "dependency_missing",
    "unsupported_action",
)
KNOWN_RETRY_BRANCHES = (
    "url_fetch",
    "get_image_api",
    "get_file_api",
    "refresh_nc_get_rkey",
    "refresh_get_msg",
)


class ImageContextService:
    """从最近消息中提取图片信息，生成可注入回复的上下文摘要。"""

    def __init__(
        self,
        *,
        config: Union[PersonaConfig, Dict[str, Any]],
        image_resolver: Any,
        image_understander: Any,
        message_repo: Any,
        module_metric_event_callback: Any = None,
    ) -> None:
        self.config = config
        self.image_resolver = image_resolver
        self.image_understander = image_understander
        self.message_repo = message_repo
        self.module_metric_event_callback = module_metric_event_callback

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
        zero_resolved_via_stats = {key: 0 for key in KNOWN_RESOLVED_VIAS}
        zero_error_stats = {key: 0 for key in KNOWN_ERROR_CATEGORIES}
        zero_retry_stats = {key: 0 for key in KNOWN_RETRY_BRANCHES}
        if not recent_messages:
            self._log_build_metrics(
                conv_id,
                images=0,
                image_cache_hit=0,
                analyzed=0,
                image_understanding_cost=0,
                resolved_via_count=zero_resolved_via_stats,
                error_category_count=zero_error_stats,
                retry_count_by_branch=zero_retry_stats,
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
                resolved_via_count=zero_resolved_via_stats,
                error_category_count=zero_error_stats,
                retry_count_by_branch=zero_retry_stats,
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
        resolved_via_count = {key: 0 for key in KNOWN_RESOLVED_VIAS}
        error_category_count = {key: 0 for key in KNOWN_ERROR_CATEGORIES}
        retry_count_by_branch = {key: 0 for key in KNOWN_RETRY_BRANCHES}
        image_understanding_cost = 0

        for index, entry in enumerate(candidates):
            cached_summary = self._read_cached_summary(entry["image"]) if cache_enabled else ""
            if cached_summary:
                summary_slots[index] = cached_summary
                cache_hit += 1
                continue

            resolve_telemetry: Dict[str, Any] = {}
            resolved = await self.image_resolver.resolve(
                conv_id=conv_id,
                message_id=entry["message_id"],
                image_meta=entry["image"],
                onebot_self_id=self._extract_onebot_self_id(entry["metadata"]),
                onebot_message_id=self._extract_onebot_message_id(entry["metadata"]),
                telemetry=resolve_telemetry,
            )
            self._merge_metric_count(
                target=error_category_count,
                source=resolve_telemetry.get("error_category_count"),
            )
            self._merge_metric_count(
                target=retry_count_by_branch,
                source=resolve_telemetry.get("retry_count_by_branch"),
            )
            request_id = uuid.uuid4().hex
            if not resolved:
                resolved_via_count["failed"] = resolved_via_count.get("failed", 0) + 1
                if cache_enabled:
                    self._write_understanding(
                        entry["image"],
                        summary="",
                        resolved_via="failed",
                        error="resolve_failed",
                    )
                    self._mark_pending_metadata(entry, pending_metadata_updates)
                await self._emit_image_fetch_summary_event(
                    conv_id=conv_id,
                    message_id=entry.get("message_id"),
                    request_id=request_id,
                    resolved_via="failed",
                    success=False,
                )
                continue

            source = str(getattr(resolved, "source", "") or "")
            if source in resolved_via_count:
                resolved_via_count[source] += 1
            elif source:
                resolved_via_count[source] = resolved_via_count.get(source, 0) + 1

            payload = {
                "image_bytes": getattr(resolved, "image_bytes", b""),
                "mime": getattr(resolved, "mime", "image/jpeg"),
                "url": getattr(resolved, "original_url", ""),
            }
            pending_for_understanding.append((index, entry, payload, source))
            await self._emit_image_fetch_summary_event(
                conv_id=conv_id,
                message_id=entry.get("message_id"),
                request_id=request_id,
                resolved_via=source or "failed",
                success=bool(source),
            )

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
                    "resolved_via": item[3],
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
                            resolved_via=source,
                            error="",
                        )
                        self._mark_pending_metadata(entry, pending_metadata_updates)
                elif cache_enabled:
                    logger.warning(
                        "图片理解返回空摘要: conv_id=%s message_id=%s resolved_via=%s",
                        conv_id,
                        entry.get("message_id"),
                        source or "unknown",
                    )
                    self._write_understanding(
                        entry["image"],
                        summary="",
                        resolved_via=source,
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
            resolved_via_count=resolved_via_count,
            error_category_count=error_category_count,
            retry_count_by_branch=retry_count_by_branch,
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
        resolved_via_count: Dict[str, int],
        error_category_count: Dict[str, int],
        retry_count_by_branch: Dict[str, int],
    ) -> None:
        logger.info(
            "图片上下文构建完成: conv_id=%s images=%s image_cache_hit=%s analyzed=%s image_understanding_cost=%s "
            "image_resolved_via(url)=%s image_resolved_via(get_image)=%s "
            "image_resolved_via(get_file_by_file_id)=%s image_resolved_via(get_file_by_file)=%s "
            "image_resolved_via(file_id_local_path)=%s image_resolved_via(failed)=%s "
            "image_fetch_error(4xx)=%s image_fetch_error(5xx)=%s image_fetch_error(timeout)=%s "
            "image_fetch_error(network)=%s image_fetch_error(dependency_missing)=%s "
            "image_fetch_error(unsupported_action)=%s image_fetch_retry(url_fetch)=%s "
            "image_fetch_retry(get_image_api)=%s image_fetch_retry(get_file_api)=%s "
            "image_fetch_retry(refresh_nc_get_rkey)=%s image_fetch_retry(refresh_get_msg)=%s",
            conv_id,
            images,
            image_cache_hit,
            analyzed,
            image_understanding_cost,
            resolved_via_count.get("url", 0),
            resolved_via_count.get("get_image", 0),
            resolved_via_count.get("get_file_by_file_id", 0),
            resolved_via_count.get("get_file_by_file", 0),
            resolved_via_count.get("file_id_local_path", 0),
            resolved_via_count.get("failed", 0),
            error_category_count.get("4xx", 0),
            error_category_count.get("5xx", 0),
            error_category_count.get("timeout", 0),
            error_category_count.get("network", 0),
            error_category_count.get("dependency_missing", 0),
            error_category_count.get("unsupported_action", 0),
            retry_count_by_branch.get("url_fetch", 0),
            retry_count_by_branch.get("get_image_api", 0),
            retry_count_by_branch.get("get_file_api", 0),
            retry_count_by_branch.get("refresh_nc_get_rkey", 0),
            retry_count_by_branch.get("refresh_get_msg", 0),
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

            ordered_images: List[Tuple[int, int, Dict[str, Any]]] = []
            for fallback_index, image in enumerate(images):
                if not isinstance(image, dict):
                    continue
                segment_index = image.get("segment_index")
                try:
                    order = int(segment_index)
                except (TypeError, ValueError):
                    order = 10**9 + fallback_index
                ordered_images.append((order, fallback_index, image))
            ordered_images.sort(key=lambda item: (item[0], item[1]))

            for _, _, image in ordered_images:
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
    def _extract_onebot_self_id(metadata: Dict[str, Any]) -> str:
        onebot = metadata.get("onebot")
        if not isinstance(onebot, dict):
            return ""
        return str(onebot.get("self_id") or "").strip()

    @staticmethod
    def _extract_onebot_message_id(metadata: Dict[str, Any]) -> str:
        onebot = metadata.get("onebot")
        if not isinstance(onebot, dict):
            return ""
        return str(onebot.get("message_id") or "").strip()

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
        resolved_via: str,
        error: str,
    ) -> None:
        payload = {
            "summary": summary,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if resolved_via:
            payload["resolved_via"] = resolved_via
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

    @staticmethod
    def _merge_metric_count(*, target: Dict[str, int], source: Any) -> None:
        if not isinstance(source, dict):
            return
        for key, value in source.items():
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            target[key] = target.get(key, 0) + count

    async def _emit_image_fetch_summary_event(
        self,
        *,
        conv_id: str,
        message_id: Any,
        request_id: str,
        resolved_via: str,
        success: bool,
    ) -> None:
        callback = self.module_metric_event_callback
        if callback is None:
            return
        event = {
            "module_id": "persona.image_fetch",
            "plugin_name": "persona",
            "module_name": "image_fetch",
            "operation": "image_fetch",
            "phase": "image_fetch",
            "resolved_via": resolved_via,
            "conv_id": conv_id,
            "message_id": str(message_id) if message_id is not None else None,
            "request_id": request_id,
            "success": success,
        }
        try:
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.warning(
                "图片拉取 summary 事件写入失败: conv_id=%s message_id=%s request_id=%s error=%s",
                conv_id,
                message_id,
                request_id,
                exc,
            )
