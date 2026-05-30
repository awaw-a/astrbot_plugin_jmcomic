from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .jm_adapter import JmcomicAdapter
    from .plugin_config import PluginConfig
    from .task_manager import TaskManager
except ImportError:
    from jm_adapter import JmcomicAdapter
    from plugin_config import PluginConfig
    from task_manager import TaskManager


@register("astrbot_plugin_jmcomic", "Codex", "基于 JMComic-Crawler-Python 的 JMComic 下载插件", "1.0.0")
class JMComicPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.root_dir = Path(__file__).resolve().parent
        self.astrbot_config = config
        self.config: Optional[PluginConfig] = None
        self.adapter: Optional[JmcomicAdapter] = None
        self.tasks: Optional[TaskManager] = None

    async def initialize(self):
        self.config = PluginConfig.load(self.astrbot_config or self.context, self.root_dir)
        self.adapter = JmcomicAdapter(self.config, self.root_dir)
        self.tasks = TaskManager(self.config, self.adapter, self.context)
        await self.tasks.start()
        logger.info("astrbot_plugin_jmcomic initialized")

    async def terminate(self):
        if self.tasks is not None:
            await self.tasks.stop()

    @filter.command("jm")
    async def jm_download_album(self, event: AstrMessageEvent):
        """下载整本 JM album。"""
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
            yield event.plain_result("用法：/jm <album_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            if self.config.send_detail_before_download:  # type: ignore[union-attr]
                album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
                yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
            task = await self.tasks.submit("album", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"已加入下载队列：{task.label}，任务ID：{task.task_id}")
        except Exception as exc:
            logger.error("jm command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 请求失败：{exc}")

    @filter.command("jmp")
    async def jm_download_photo(self, event: AstrMessageEvent):
        """下载单个 JM 章节/photo。"""
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
            yield event.plain_result("用法：/jmp <photo_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            task = await self.tasks.submit("photo", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"已加入下载队列：{task.label}，任务ID：{task.task_id}")
        except Exception as exc:
            logger.error("jmp command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 请求失败：{exc}")

    @filter.command("jm_info")
    async def jm_info(self, event: AstrMessageEvent):
        """查看 JM album 详情，不下载。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        raw = self._arg_text(event, "jm_info")
        if not raw:
            yield event.plain_result("用法：/jm_info <album_id>")
            return

        try:
            jm_id = self.adapter.parse_jm_id(raw)  # type: ignore[union-attr]
            album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
            yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("jm_info command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 详情获取失败：{exc}")

    @filter.command("jm_search")
    async def jm_search(self, event: AstrMessageEvent):
        """搜索 JM album。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        keyword = self._arg_text(event, "jm_search")
        if not keyword:
            yield event.plain_result("用法：/jm_search <关键词>")
            return

        try:
            limit = self.config.max_search_results  # type: ignore[union-attr]
            items = await asyncio.to_thread(self.adapter.search, keyword, limit)  # type: ignore[union-attr]
            if not items:
                yield event.plain_result("没有搜索结果。")
                return

            lines = [f"搜索结果：{keyword}"]
            for item in items:
                tags = ", ".join(item.tags[:5])
                suffix = f" [{tags}]" if tags else ""
                lines.append(f"JM{item.album_id} - {item.title}{suffix}")
            yield event.plain_result("\n".join(lines))
        except Exception as exc:
            logger.error("jm_search command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 搜索失败：{exc}")

    @filter.command("jm_queue")
    async def jm_queue(self, event: AstrMessageEvent):
        """查看最近的 JM 下载任务。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return
        yield event.plain_result(self.tasks.format_queue())  # type: ignore[union-attr]

    @filter.command("jm_cancel")
    async def jm_cancel(self, event: AstrMessageEvent):
        """取消 JM 下载任务。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        task_id = self._arg_text(event, "jm_cancel").strip()
        if not task_id:
            yield event.plain_result("用法：/jm_cancel <任务ID>")
            return
        task = self.tasks.cancel(task_id)  # type: ignore[union-attr]
        if task is None:
            yield event.plain_result(f"未找到任务：{task_id}")
        elif task.status == "cancelled":
            yield event.plain_result(f"已取消任务：{task.task_id}")
        else:
            yield event.plain_result(f"任务 {task.task_id} 已标记取消，会在当前下载步骤结束后停止后续处理。")

    @filter.command("jm_clean")
    async def jm_clean(self, event: AstrMessageEvent):
        """清理过期的 JM 下载和导出文件。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        err = self._check_policy(event)
        if err is not None:
            yield event.plain_result(err)
            return

        removed = self.tasks.cleanup()  # type: ignore[union-attr]
        yield event.plain_result(f"已清理 {removed} 个过期 JM 输出项。")

    def _require_ready(self) -> Optional[str]:
        if self.config is None or self.adapter is None or self.tasks is None:
            return "JMComic 插件尚未初始化完成。"
        if not self.config.enabled:
            return "JMComic 插件已禁用。"
        return None

    def _check_policy(self, event: AstrMessageEvent) -> Optional[str]:
        assert self.config is not None
        if not self.config.allow_group and self._is_group_event(event):
            return "当前配置不允许在群聊中使用 JM 下载。"
        if self.config.admin_only and not self._is_admin_event(event):
            return "当前配置仅允许管理员使用 JM 下载指令。"
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
