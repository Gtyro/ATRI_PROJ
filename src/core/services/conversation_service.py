"""对话处理服务。"""

import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Union

from ..domain import PersonaConfig
from ..ports import LongTermMemoryPort, ShortTermMemoryPort
from .persona_policy_flags import (
    LLM_ACTIVE_REPLY_ENABLED_KEY,
    LLM_PASSIVE_REPLY_ENABLED_KEY,
    LLM_TOPIC_EXTRACT_ENABLED_KEY,
    resolve_llm_flags,
)
from .plugin_policy_service import PluginPolicyService


class ConversationService:
    """负责消息入库、话题提取与回复生成的服务。"""

    def __init__(
        self,
        short_term: ShortTermMemoryPort,
        long_term: LongTermMemoryPort,
        msgprocessor: Any,
        message_repo: Any,
        group_config: Any,
        plugin_name: str,
        config: Union[PersonaConfig, Dict[str, Any]],
        reply_callback: Optional[Callable] = None,
        plugin_policy_service: Optional[PluginPolicyService] = None,
        image_context_service: Optional[Any] = None,
    ) -> None:
        self.short_term = short_term
        self.long_term = long_term
        self.msgprocessor = msgprocessor
        self.message_repo = message_repo
        self.group_config = group_config
        self.plugin_name = plugin_name
        self.config = config
        self.reply_callback = reply_callback
        self.plugin_policy_service = plugin_policy_service
        self.image_context_service = image_context_service

    def _queue_history_size(self) -> int:
        if isinstance(self.config, PersonaConfig):
            return self.config.queue_history_size
        if "queue_history_size" not in self.config:
            raise ValueError("queue_history_size 未配置")
        return int(self.config["queue_history_size"])

    def _batch_interval(self) -> int:
        if isinstance(self.config, PersonaConfig):
            return self.config.batch_interval
        if "batch_interval" not in self.config:
            raise ValueError("batch_interval 未配置")
        return int(self.config["batch_interval"])

    def set_reply_callback(self, reply_callback: Optional[Callable]) -> None:
        self.reply_callback = reply_callback

    def _image_understanding_enabled(self) -> bool:
        if isinstance(self.config, PersonaConfig):
            return bool(self.config.image_understanding.enabled)

        image_cfg = self.config.get("image_understanding", {})
        if isinstance(image_cfg, dict):
            return bool(image_cfg.get("enabled", True))
        return True

    def _configured_retrieval_ab_mode(self) -> str:
        mode = "tool_only"
        if isinstance(self.config, PersonaConfig):
            mode = str(self.config.image_understanding.retrieval_ab_mode)
        else:
            image_cfg = self.config.get("image_understanding", {})
            if isinstance(image_cfg, dict):
                mode = str(image_cfg.get("retrieval_ab_mode", "tool_only"))
        normalized = mode.strip().lower() or "tool_only"
        if normalized not in {"tool_only", "hybrid"}:
            raise ValueError(f"未知 retrieval_ab_mode={normalized}，仅支持 tool_only 或 hybrid")
        return normalized

    @staticmethod
    def _merge_long_memory_prompt(base_prompt: str, extra_prompt: str) -> str:
        base = (base_prompt or "").strip()
        extra = (extra_prompt or "").strip()
        if not extra:
            return base
        if not base:
            return extra
        return f"{base}\n\n{extra}"

    @staticmethod
    def _resolve_tool_choice(retrieval_ab_mode: str) -> str:
        mode = str(retrieval_ab_mode or "").strip().lower()
        if mode == "hybrid":
            return "none"
        if mode == "tool_only":
            return "required"
        raise ValueError(f"未知 retrieval_ab_mode={mode}，无法决定 tool_choice")

    @staticmethod
    def _inject_image_summaries(messages: List[Dict[str, Any]]) -> int:
        """将识图摘要注入消息 content，替换 [图片] 占位符。"""
        injected_count = 0
        for message in messages:
            if not isinstance(message, dict):
                continue

            content = str(message.get("content") or "")
            if "[图片]" not in content:
                continue
            if "[图片内容:" in content:
                continue

            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            media = metadata.get("media")
            if not isinstance(media, dict):
                continue
            images = media.get("images")
            if not isinstance(images, list) or not images:
                continue

            ordered_summaries: List[tuple[int, int, str]] = []
            for fallback_index, image in enumerate(images):
                if not isinstance(image, dict):
                    continue
                understanding = image.get("understanding")
                if not isinstance(understanding, dict):
                    continue
                summary = str(understanding.get("summary") or "").strip()
                if not summary:
                    continue
                segment_index = image.get("segment_index")
                try:
                    order = int(segment_index)
                except (TypeError, ValueError):
                    order = 10**9 + fallback_index
                ordered_summaries.append((order, fallback_index, summary))

            if not ordered_summaries:
                continue

            ordered_summaries.sort(key=lambda item: (item[0], item[1]))
            summaries = [item[2] for item in ordered_summaries]
            placeholder_count = content.count("[图片]")
            if placeholder_count <= 0:
                continue

            if placeholder_count == 1:
                merged_summaries: List[str] = []
                seen = set()
                for summary in summaries:
                    if summary in seen:
                        continue
                    seen.add(summary)
                    merged_summaries.append(summary)
                summary_text = "；".join(merged_summaries[:3])
                replacement = f"[图片内容: {summary_text}]"
                new_content = content.replace("[图片]", replacement, 1)
            else:
                index = 0

                def _replace_placeholder(_: re.Match) -> str:
                    nonlocal index
                    if index < len(summaries):
                        summary = summaries[index]
                        index += 1
                        return f"[图片内容: {summary}]"
                    index += 1
                    return "[图片]"

                new_content = re.sub(re.escape("[图片]"), _replace_placeholder, content)

            normalized = re.sub(r"\s{2,}", " ", new_content).strip()
            if normalized == content.strip():
                continue
            message["content"] = normalized
            injected_count += 1

        return injected_count

    @staticmethod
    def _split_reply_content(reply_content: Optional[str]) -> List[str]:
        """按短句切分回复，保留括号旁白为独立片段并过滤空消息。"""
        if not reply_content:
            return []

        # Keep spaces inside English multi-word phrases such as "TOGENASHI TOGEARI".
        en_multi_word = (
            r"[A-Za-z0-9][A-Za-z0-9'._+-]*"
            r"(?:\s+[A-Za-z0-9][A-Za-z0-9'._+-]*)+"
            r"(?:[^，。！？（）()\s]+)?"
        )
        token_pattern = re.compile(
            rf"\(.*?\)|（.*?）|{en_multi_word}\.+|{en_multi_word}|"
            r"[^，。！？（）()\s]+\.+|[^，。！？（）()\s]+"
        )
        split_replies = [
            match.group(0).strip()
            for match in token_pattern.finditer(reply_content)
            if match.group(0).strip()
        ]

        if not split_replies and reply_content.strip():
            split_replies.append(reply_content.strip())

        return split_replies

    async def _is_group_ingest_enabled(self, conv_id: str) -> bool:
        if not self.plugin_policy_service or not conv_id.startswith("group_"):
            return True
        group_id = conv_id.split("_", 1)[1]
        return await self.plugin_policy_service.is_ingest_enabled(group_id, self.plugin_name)

    async def _is_group_enabled(self, conv_id: str) -> bool:
        if not self.plugin_policy_service or not conv_id.startswith("group_"):
            return True
        group_id = conv_id.split("_", 1)[1]
        return await self.plugin_policy_service.is_enabled(group_id, self.plugin_name)

    async def _get_llm_flags(self, conv_id: str) -> Dict[str, bool]:
        if not self.plugin_policy_service or not conv_id.startswith("group_"):
            return resolve_llm_flags({})
        group_id = conv_id.split("_", 1)[1]
        policy = await self.plugin_policy_service.get_policy(group_id, self.plugin_name)
        return resolve_llm_flags(policy.config or {})

    async def _defer_next_process(self, conv_id: str) -> None:
        if not conv_id.startswith("group_"):
            return
        group_id = conv_id.split("_")[1]
        gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
        plugin_config = gpconfig.plugin_config or {}
        plugin_config["next_process_time"] = time.time() + self._batch_interval()
        gpconfig.plugin_config = plugin_config
        await gpconfig.save()

    async def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理新消息并按需触发会话处理。"""
        try:
            conv_id = message_data.get("conv_id", "")
            if not await self._is_group_ingest_enabled(conv_id):
                logging.info(f"会话 {conv_id} 已关闭入库，跳过处理")
                return None
            await self.short_term.add_message(message_data)
        except Exception as e:
            logging.error(f"persona_system.process_message:添加消息到短期记忆失败: {e}")
            raise e

        try:
            if message_data["is_direct"]:
                return await self.process_conversation(
                    message_data["conv_id"],
                    message_data["user_id"],
                    message_data["is_direct"],
                )
        except Exception as e:
            logging.error(f"persona_system.process_message:处理消息失败: {e}")
            raise e

        return None

    async def process_conversation(
        self,
        conv_id: str,
        user_id: str,
        is_direct: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """处理特定会话的消息。"""
        try:
            if not await self._is_group_enabled(conv_id):
                logging.info(f"会话 {conv_id} 插件已禁用，跳过处理")
                return None
            llm_flags = await self._get_llm_flags(conv_id)
            pending_threshold = self._queue_history_size()
            if conv_id.startswith("group_") and not is_direct:
                pending_messages = await self.short_term.get_unprocessed_messages(
                    conv_id,
                    pending_threshold,
                )
                pending_count = len(pending_messages)
                if pending_count < pending_threshold:
                    logging.info(
                        f"会话 {conv_id} 未处理消息不足 {pending_threshold} 条（当前 {pending_count} 条），跳过处理"
                    )
                    return None
            message_count = 0
            memory_count = 0
            marked_count_total = 0
            loop_count = 0
            topics: List[Dict[str, Any]] = []
            messages: List[Dict[str, Any]] = []
            if not llm_flags.get(LLM_TOPIC_EXTRACT_ENABLED_KEY, True):
                logging.info(f"会话 {conv_id} 已关闭记忆提取，仅用于回复判断")
                messages = await self.short_term.get_unprocessed_messages(
                    conv_id,
                    2 * self._queue_history_size(),
                )
                if not messages:
                    logging.info(f"会话 {conv_id} 没有未处理消息")
                    return None
                message_count = len(messages)
            else:
                while True:
                    loop_count += 1
                    messages = await self.short_term.get_unprocessed_messages(
                        conv_id,
                        2 * self._queue_history_size(),
                    )
                    if not messages:
                        logging.info(f"会话 {conv_id} 没有未处理消息")
                        return None
                    message_count += len(messages)

                    topics = await self.msgprocessor.extract_topics_from_messages(conv_id, messages)
                    if len(topics) == 0:
                        break

                    memory_ids = await self.long_term.store_memories(conv_id, topics)
                    memory_count += len(memory_ids)
                    if len(memory_ids) == 0:
                        break

                    marked_count = await self.short_term.mark_processed(conv_id, topics)
                    marked_count_total += marked_count

                    if len(messages) < 2 * self._queue_history_size():
                        break
                    if len(topics) == 0 or len(memory_ids) == 0 or marked_count == 0:
                        logging.warning(
                            f"会话 {conv_id} 处理异常，有 {len(topics)} 个话题，"
                            f"{len(memory_ids)} 个记忆，{marked_count} 条消息被标记为已处理"
                        )
                        break
                    logging.info(
                        f"会话 {conv_id} 第{loop_count}次循环: 处理了 {len(messages)} 条消息，"
                        f"存储了 {len(memory_ids)} 个记忆，标记了 {marked_count} 条消息为已处理"
                    )

            logging.info(
                f"会话 {conv_id} 处理完成: 共 {loop_count} 次循环，处理了 {message_count} 条消息，"
                f"存储了 {memory_count} 个记忆，标记了 {marked_count_total} 条消息为已处理"
            )
        except Exception as e:
            logging.error(f"会话 {conv_id} 处理失败: {e}")
            raise e

        should_reply = await self.msgprocessor.should_respond(conv_id, topics)
        has_bot_message = await self.message_repo.has_bot_message(conv_id)
        if has_bot_message:
            logging.info(f"会话 {conv_id} 已有机器人发的消息，不回复")
            should_reply = False
        if len(messages) >= 2 * self._queue_history_size():
            logging.info(f"会话 {conv_id} 消息未处理完，不回复")
            should_reply = False
        if is_direct:
            should_reply = True
            if not llm_flags.get(LLM_PASSIVE_REPLY_ENABLED_KEY, False):
                should_reply = False
                logging.info(f"会话 {conv_id} 已关闭被动回复，跳过回复")
        else:
            if not llm_flags.get(LLM_ACTIVE_REPLY_ENABLED_KEY, False):
                should_reply = False
                logging.info(f"会话 {conv_id} 已关闭主动回复，跳过回复")

        if not should_reply:
            if conv_id.startswith("group_"):
                cooldown_seconds = self._batch_interval()
                logging.info(
                    "会话 %s 不需要回复，下次处理时间设置为 %d 秒",
                    conv_id,
                    cooldown_seconds,
                )
                group_id = conv_id.split("_")[1]
                gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
                gpconfig.plugin_config["next_process_time"] = time.time() + cooldown_seconds
                await gpconfig.save()
            return None

        retrieval_ab_mode = self._configured_retrieval_ab_mode()
        logging.info("会话 %s 检索模式: ab_mode=%s", conv_id, retrieval_ab_mode)

        logging.info(f"会话 {conv_id} 需要回复")

        recent_messages = await self.short_term.get_recent_messages(
            conv_id,
            self._queue_history_size(),
        )
        logging.info(f"会话 {conv_id} 获取最近消息历史完成")

        long_memory_prompt = ""
        explicit_memory_hit = False
        if self._image_understanding_enabled():
            if self.image_context_service is None:
                logging.warning(f"会话 {conv_id} 已开启图片理解，但 image_context_service 未装配")
            else:
                try:
                    image_context = await self.image_context_service.build_context(conv_id, recent_messages)
                    if image_context:
                        long_memory_prompt = image_context
                        logging.info(f"会话 {conv_id} 已注入图片上下文")
                except Exception as e:
                    logging.error(f"会话 {conv_id} 构建图片上下文失败: {e}")

            summary_injected = self._inject_image_summaries(recent_messages)
            if summary_injected > 0:
                logging.info(
                    "会话 %s 图片摘要已注入消息历史: image_summary_injected=%d",
                    conv_id,
                    summary_injected,
                )

        reply_keywords: List[str] = []
        if retrieval_ab_mode == "hybrid":
            try:
                reply_keywords = await self.msgprocessor.extract_reply_keywords_from_history(
                    conv_id,
                    recent_messages,
                )
                if reply_keywords:
                    logging.info(f"会话 {conv_id} 回复关键词: {reply_keywords}")
            except Exception as e:
                logging.error(f"会话 {conv_id} 回复关键词提取失败: {e}")
        keyword_count = len(reply_keywords)
        logging.info(
            "会话 %s 回复关键词统计: ab_mode=%s keyword_count=%d",
            conv_id,
            retrieval_ab_mode,
            keyword_count,
        )

        if retrieval_ab_mode == "hybrid":
            try:
                memory_context = await self.msgprocessor.retrieve_memory_context(conv_id, reply_keywords)
                if memory_context and "我似乎没有关于这方面的记忆" not in memory_context:
                    explicit_memory_hit = True
                    long_memory_prompt = self._merge_long_memory_prompt(
                        long_memory_prompt,
                        f"以下是显式检索到的历史记忆，请优先参考:\n{memory_context}",
                    )
                    logging.info("会话 %s hybrid 模式注入显式记忆上下文", conv_id)
            except Exception as e:
                logging.error(f"会话 {conv_id} hybrid 显式记忆检索失败: {e}")
        memory_hit_count = 1 if explicit_memory_hit else 0
        logging.info(
            "会话 %s 显式记忆统计: ab_mode=%s keyword_count=%d memory_hit_count=%d",
            conv_id,
            retrieval_ab_mode,
            keyword_count,
            memory_hit_count,
        )

        tool_choice = self._resolve_tool_choice(retrieval_ab_mode)
        logging.info(
            "会话 %s 回复工具策略: ab_mode=%s memory_context_hit=%s tool_choice=%s",
            conv_id,
            retrieval_ab_mode,
            explicit_memory_hit,
            tool_choice,
        )

        try:
            if conv_id.startswith("group_"):
                group_id = conv_id.split("_")[1]
                gpconfig = await self.group_config.get_config(group_id, self.plugin_name)
                gpconfig.plugin_config["next_process_time"] = time.time() + self._batch_interval()
                await gpconfig.save()
                logging.info(f"会话 {conv_id} 调整下次处理时间完成")
        except Exception as e:
            logging.error(f"会话 {conv_id} 调整下次处理时间失败: {e}")
            raise e

        reply_content = await self.msgprocessor.generate_reply(
            conv_id,
            recent_messages,
            temperature=0.7,
            long_memory_prompt=long_memory_prompt,
            tool_choice=tool_choice,
        )
        logging.info(f"会话 {conv_id} 生成回复完成")
        logging.info(f"会话 {conv_id} 回复内容: {reply_content}")

        if reply_content:
            await self.short_term.add_bot_message(conv_id, reply_content)
            logging.info(f"会话 {conv_id} 添加机器人自己的消息到历史完成")

        split_replies = self._split_reply_content(reply_content)
        reply_dict = {
            "reply_content": split_replies,
            "user_id": user_id,
        }
        if reply_content and self.reply_callback:
            await self.reply_callback(conv_id, reply_dict)

        return reply_dict
