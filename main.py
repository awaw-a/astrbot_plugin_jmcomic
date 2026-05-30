from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .file_utils import list_saved_items, size_mb
    from .jm_adapter import JmcomicAdapter
    from .plugin_config import PluginConfig
    from .task_manager import TaskManager
except ImportError:
    from file_utils import list_saved_items, size_mb
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

    @filter.command("jm", priority=100)
    async def jm_command(self, event: AstrMessageEvent):
        """下载整本 JM album。"""
        async for result in self.jm_download_album(event):
            yield result
        self._stop_event(event)

    @filter.command("jmp", priority=100)
    async def jmp_command(self, event: AstrMessageEvent):
        """下载单个 JM 章节/photo。"""
        async for result in self.jm_download_photo(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_info", priority=100)
    async def jm_info_command(self, event: AstrMessageEvent):
        """查看 JM album 详情。"""
        async for result in self.jm_info(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_search", priority=100)
    async def jm_search_command(self, event: AstrMessageEvent):
        """搜索 JM album。"""
        async for result in self.jm_search(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_queue", priority=100)
    async def jm_queue_command(self, event: AstrMessageEvent):
        """查看最近任务。"""
        async for result in self.jm_queue(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_cancel", priority=100)
    async def jm_cancel_command(self, event: AstrMessageEvent):
        """取消 JM 下载任务。"""
        async for result in self.jm_cancel(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_clean", priority=100)
    async def jm_clean_command(self, event: AstrMessageEvent):
        """清理过期的 JM 文件。"""
        async for result in self.jm_clean(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_files", priority=100)
    async def jm_files_command(self, event: AstrMessageEvent):
        """查看当前保存的 JM 文件。"""
        async for result in self.jm_files(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_test_push", priority=100)
    async def jm_test_push_command(self, event: AstrMessageEvent):
        """测试主动推送。"""
        async for result in self.jm_test_push(event):
            yield result
        self._stop_event(event)

    @filter.command("jm_help", priority=100)
    async def jm_help_command(self, event: AstrMessageEvent):
        """查看 JMComic 插件帮助。"""
        async for result in self.jm_help(event):
            yield result
        self._stop_event(event)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_jm_message(self, event: AstrMessageEvent):
        """手动解析 JM 指令，确保参数错误时也能反馈。"""
        command = self._command_name(event)
        known_commands = {
            "jm",
            "jmp",
            "jm_info",
            "jm_search",
            "jm_queue",
            "jm_cancel",
            "jm_clean",
            "jm_files",
            "jm_test_push",
            "jm_help",
        }
        if command not in known_commands:
            if command.startswith("jm"):
                yield event.plain_result(f"未知的 JM 指令：/{command}\n请使用 /jm_help 查看所有可用指令。")
                self._stop_event(event)
            return

        if command == "jm":
            async for result in self.jm_download_album(event):
                yield result
        elif command == "jmp":
            async for result in self.jm_download_photo(event):
                yield result
        elif command == "jm_info":
            async for result in self.jm_info(event):
                yield result
        elif command == "jm_search":
            async for result in self.jm_search(event):
                yield result
        elif command == "jm_queue":
            async for result in self.jm_queue(event):
                yield result
        elif command == "jm_cancel":
            async for result in self.jm_cancel(event):
                yield result
        elif command == "jm_clean":
            async for result in self.jm_clean(event):
                yield result
        elif command == "jm_files":
            async for result in self.jm_files(event):
                yield result
        elif command == "jm_test_push":
            async for result in self.jm_test_push(event):
                yield result
        elif command == "jm_help":
            async for result in self.jm_help(event):
                yield result

        self._stop_event(event)

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
            yield event.plain_result(f"已收到整本下载请求：JM{jm_id}，正在处理。")
            if self.config.send_detail_before_download:  # type: ignore[union-attr]
                album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
                yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
            task = await self.tasks.submit("album", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"已加入下载队列：{task.label}，任务ID：{task.task_id}。后续状态会主动推送，也可使用 /jm_queue 查询。")
        except Exception as exc:
            logger.error("jm command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 请求失败：{exc}\n请使用 /jm_help 查看指令用法。")

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
            yield event.plain_result(f"已收到章节下载请求：PHOTO{jm_id}，正在加入队列。")
            task = await self.tasks.submit("photo", jm_id, event)  # type: ignore[union-attr]
            yield event.plain_result(f"已加入下载队列：{task.label}，任务ID：{task.task_id}。后续状态会主动推送，也可使用 /jm_queue 查询。")
        except Exception as exc:
            logger.error("jmp command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 请求失败：{exc}\n请使用 /jm_help 查看指令用法。")

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
            yield event.plain_result(f"已收到详情查询请求：JM{jm_id}，正在查询。")
            album = await asyncio.to_thread(self.adapter.get_album_info, jm_id)  # type: ignore[union-attr]
            yield event.plain_result(self.adapter.format_album_info(album))  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("jm_info command failed: %s", exc, exc_info=exc)
            yield event.plain_result(f"JM 详情获取失败：{exc}\n请使用 /jm_help 查看指令用法。")

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
            yield event.plain_result(f"已收到搜索请求：{keyword}，正在搜索。")
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
            yield event.plain_result(f"JM 搜索失败：{exc}\n请使用 /jm_help 查看指令用法。")

    async def jm_queue(self, event: AstrMessageEvent):
        """查看最近的 JM 下载任务。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return
        yield event.plain_result(self.tasks.format_queue())  # type: ignore[union-attr]

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

    async def jm_files(self, event: AstrMessageEvent):
        """查看当前系统保存的 JM 文件。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        raw = self._arg_text(event, "jm_files").strip()
        try:
            limit = int(raw) if raw else 30
        except ValueError:
            yield event.plain_result("用法：/jm_files [显示数量]")
            return

        limit = max(1, min(limit, 100))
        items, total_count, total_size = list_saved_items(
            [self.config.download_dir, self.config.export_dir],  # type: ignore[union-attr]
            limit=limit,
        )

        if total_count == 0:
            yield event.plain_result("当前没有保存的 JM 文件。")
            return

        lines = [
            f"当前保存项：{total_count} 个，总大小：{size_mb(total_size)} MB",
            f"下载目录：{self.config.download_dir}",  # type: ignore[union-attr]
            f"导出目录：{self.config.export_dir}",  # type: ignore[union-attr]
            f"最近 {len(items)} 项：",
        ]
        for item in items:
            kind = "目录" if item.is_dir else "文件"
            root_name = "downloads" if item.root == self.config.download_dir else "exports"  # type: ignore[union-attr]
            lines.append(
                f"- [{root_name}/{kind}] {item.relative_name} | {size_mb(item.size)} MB | {item.modified_text}"
            )

        if total_count > len(items):
            lines.append(f"还有 {total_count - len(items)} 项未显示，可用 /jm_files 100 查看更多。")

        yield event.plain_result("\n".join(lines))

    async def jm_test_push(self, event: AstrMessageEvent):
        """测试当前会话是否支持主动推送。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        origin = getattr(event, "unified_msg_origin", "") or ""
        if not origin:
            yield event.plain_result("当前事件没有 unified_msg_origin，无法测试主动推送。")
            return

        yield event.plain_result("已收到主动推送测试请求。3 秒后会尝试主动发送一条消息。")
        asyncio.create_task(self._delayed_test_push(origin))

    async def _delayed_test_push(self, origin: str):
        await asyncio.sleep(3)
        try:
            from astrbot.api.event import MessageChain

            chain = MessageChain().message("JMComic 主动推送测试成功：当前会话支持 context.send_message。")
        except Exception:
            chain = ["JMComic 主动推送测试成功：当前会话支持 context.send_message。"]

        try:
            await self.context.send_message(origin, chain)
        except Exception as exc:
            logger.error("jm_test_push failed: %s", exc, exc_info=exc)

    async def jm_help(self, event: AstrMessageEvent):
        """查看 JMComic 插件帮助。"""
        ready = self._require_ready()
        if ready is not None:
            yield event.plain_result(ready)
            return

        if self.config.zip_password_enabled:  # type: ignore[union-attr]
            password_text = f"当前压缩包密码：{self.config.zip_password}"  # type: ignore[union-attr]
        else:
            password_text = "当前压缩包密码：未启用"

        yield event.plain_result(
            "\n".join(
                [
                    "JMComic 插件可用指令：",
                    "/jm <album_id> - 下载整本 album",
                    "/jmp <photo_id> - 下载单个章节/photo",
                    "/jm_info <album_id> - 查看 album 详情，不下载",
                    "/jm_search <关键词> - 搜索 album",
                    "/jm_queue - 查看最近任务",
                    "/jm_cancel <任务ID> - 取消任务",
                    "/jm_files [显示数量] - 查看当前保存的下载和导出文件",
                    "/jm_clean - 清理过期下载和导出文件",
                    "/jm_test_push - 测试当前会话是否支持主动推送",
                    "/jm_help - 查看本帮助",
                    "",
                    password_text,
                ]
            )
        )

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
    def _stop_event(event: AstrMessageEvent):
        stop = getattr(event, "stop_event", None)
        if callable(stop):
            stop()

    @staticmethod
    def _command_name(event: AstrMessageEvent) -> str:
        text = getattr(event, "message_str", "") or ""
        text = text.strip()
        if not text.startswith("/"):
            return ""
        return text.split(maxsplit=1)[0].lstrip("/").strip()

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
