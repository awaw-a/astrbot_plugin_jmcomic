from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from jm_adapter import JmcomicAdapter
from plugin_config import PluginConfig
from task_manager import TaskManager


@register("astrbot_plugin_jmcomic", "Codex", "JMComic downloader powered by JMComic-Crawler-Python", "1.0.0")
class JMComicPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.root_dir = Path(__file__).resolve().parent
        self.config: Optional[PluginConfig] = None
        self.adapter: Optional[JmcomicAdapter] = None
        self.tasks: Optional[TaskManager] = None

    async def initialize(self):
        self.config = PluginConfig.load(self.context, self.root_dir)
        self.adapter = JmcomicAdapter(self.config, self.root_dir)
        self.tasks = TaskManager(self.config, self.adapter, self.context)
        await self.tasks.start()
        logger.info("astrbot_plugin_jmcomic initialized")

    async def terminate(self):
        if self.tasks is not None:
            await self.tasks.stop()

    @filter.command("jm")
    async def jm_download_album(self, event: AstrMessageEvent):
        """Download a JM album."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        err = self._check_policy(event)
        if err is not None:
            yield event.plain_result(err)
            return

        raw = self._arg_text(event, "jm")
        if not raw:
            yield event.plain_result("Usage: /jm <album_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            if self.config.send_detail_before_download:  # type: ignore[union-attr]
                album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
                yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
            task = await self.tasks.submit("album", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"Queued {task.label}. Task: {task.task_id}")
        except Exception as exc:
            logger.error("jm command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM request failed: {exc}")

    @filter.command("jmp")
    async def jm_download_photo(self, event: AstrMessageEvent):
        """Download a JM photo/chapter."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        err = self._check_policy(event)
        if err is not None:
            yield event.plain_result(err)
            return

        raw = self._arg_text(event, "jmp")
        if not raw:
            yield event.plain_result("Usage: /jmp <photo_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            task = await self.tasks.submit("photo", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"Queued {task.label}. Task: {task.task_id}")
        except Exception as exc:
            logger.error("jmp command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM request failed: {exc}")

    @filter.command("jm_info")
    async def jm_info(self, event: AstrMessageEvent):
        """Show JM album detail without downloading."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        raw = self._arg_text(event, "jm_info")
        if not raw:
            yield event.plain_result("Usage: /jm_info <album_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
            yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("jm_info command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM info failed: {exc}")

    @filter.command("jm_search")
    async def jm_search(self, event: AstrMessageEvent):
        """Search JM albums."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        keyword = self._arg_text(event, "jm_search")
        if not keyword:
            yield event.plain_result("Usage: /jm_search <keyword>")
            return

        try:
            limit = self.config.max_search_results  # type: ignore[union-attr]
            items = await asyncio.to_thread(self.adapter.search, keyword, limit)  # type: ignore[union-attr]
            if not items:
                yield event.plain_result("No results.")
                return

            lines = [f"Search results for: {keyword}"]
            for item in items:
                tags = ", ".join(item.tags[:5])
                suffix = f" [{tags}]" if tags else ""
                lines.append(f"JM{item.album_id} - {item.title}{suffix}")
            yield event.plain_result("\n".join(lines))
        except Exception as exc:
            logger.error("jm_search command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM search failed: {exc}")

    @filter.command("jm_queue")
    async def jm_queue(self, event: AstrMessageEvent):
        """Show recent JM tasks."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return
        yield event.plain_result(self.tasks.format_queue())  # type: ignore[union-attr]

    @filter.command("jm_cancel")
    async def jm_cancel(self, event: AstrMessageEvent):
        """Cancel a queued/running JM task."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        task_id = self._arg_text(event, "jm_cancel").strip()
        if not task_id:
            yield event.plain_result("Usage: /jm_cancel <task_id>")
            return
        task = self.tasks.cancel(task_id)  # type: ignore[union-attr]
        if task is None:
            yield event.plain_result(f"Task not found: {task_id}")
        elif task.status == "cancelled":
            yield event.plain_result(f"Cancelled task {task.task_id}.")
        else:
            yield event.plain_result(f"Task {task.task_id} will stop after the current download step.")

    @filter.command("jm_clean")
    async def jm_clean(self, event: AstrMessageEvent):
        """Clean old JM outputs."""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        err = self._check_policy(event)
        if err is not None:
            yield event.plain_result(err)
            return

        removed = self.tasks.cleanup()  # type: ignore[union-attr]
        yield event.plain_result(f"Cleaned {removed} old JM output item(s).")

    def _require_ready(self) -> Optional[str]:
        if self.config is None or self.adapter is None or self.tasks is None:
            return "JMComic plugin is not initialized yet."
        if not self.config.enabled:
            return "JMComic plugin is disabled."
        return None

    def _check_policy(self, event: AstrMessageEvent) -> Optional[str]:
        assert self.config is not None
        if not self.config.allow_group and self._is_group_event(event):
            return "JM download is disabled in group chats."
        if self.config.admin_only and not self._is_admin_event(event):
            return "Only admins can use JM download commands."
        return None

    @staticmethod
    def _arg_text(event: AstrMessageEvent, command: str) -> str:
        text = getattr(event, "message_str", "") or ""
        text = text.strip()
        if not text:
            return ""
        parts = text.split(maxsplit=1)
        head = parts[0].lstrip("/")
        if head == command:
            return parts[1].strip() if len(parts) > 1 else ""
        return text

    @staticmethod
    def _is_group_event(event: AstrMessageEvent) -> bool:
        for name in ("is_group", "is_group_message"):
            method = getattr(event, name, None)
            if callable(method):
                try:
                    return bool(method())
                except Exception:
                    pass
        if getattr(event, "group_id", None):
            return True
        message_obj = getattr(event, "message_obj", None)
        return bool(getattr(message_obj, "group_id", None))

    @staticmethod
    def _is_admin_event(event: AstrMessageEvent) -> bool:
        for name in ("is_admin", "is_operator", "is_owner"):
            method = getattr(event, name, None)
            if callable(method):
                try:
                    return bool(method())
                except Exception:
                    pass
        return False
