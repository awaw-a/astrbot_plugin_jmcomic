from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from time import time
from typing import Any, Optional

from astrbot.api import logger

try:
    from .file_utils import cleanup_old_files, is_too_large, newest_child_dir, path_size, size_mb, zip_directory
    from .jm_adapter import JmcomicAdapter
    from .models import JmTask
    from .plugin_config import PluginConfig
except ImportError:
    from file_utils import cleanup_old_files, is_too_large, newest_child_dir, path_size, size_mb, zip_directory
    from jm_adapter import JmcomicAdapter
    from models import JmTask
    from plugin_config import PluginConfig


class TaskManager:
    def __init__(self, config: PluginConfig, adapter: JmcomicAdapter, context: Any = None):
        self.config = config
        self.adapter = adapter
        self.context = context
        self.queue: asyncio.Queue = asyncio.Queue()
        self.tasks: dict[str, JmTask] = {}
        self.cancelled: set[str] = set()
        self.workers: list[asyncio.Task] = []

    async def start(self) -> None:
        if self.workers:
            return
        for index in range(self.config.max_concurrent_tasks):
            self.workers.append(asyncio.create_task(self._worker_loop(index)))

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    async def submit(self, kind: str, jm_id: str, event: Any) -> JmTask:
        user_id = str(_call_event(event, "get_sender_id", default="unknown"))
        user_name = str(_call_event(event, "get_sender_name", default=user_id))
        session_id = str(_call_event(event, "get_session_id", default="") or _event_obj_attr(event, "session_id", user_id))
        task = JmTask(
            kind=kind,  # type: ignore[arg-type]
            jm_id=jm_id,
            user_id=user_id,
            user_name=user_name,
            session_id=session_id,
            unified_msg_origin=str(getattr(event, "unified_msg_origin", "") or ""),
        )
        task.output_dir = self.config.download_dir / task.jm_id
        self.tasks[task.task_id] = task
        await self.queue.put((task, event))
        return task

    def cancel(self, task_id: str) -> Optional[JmTask]:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if task.status == "queued":
            task.status = "cancelled"
            task.finished_at = time()
        elif task.status in {"running", "packing", "sending"}:
            self.cancelled.add(task_id)
        return task

    def format_queue(self) -> str:
        if not self.tasks:
            return "暂无 JM 任务。"

        recent = sorted(self.tasks.values(), key=lambda item: item.created_at, reverse=True)[:12]
        lines = ["最近的 JM 任务："]
        for task in recent:
            extra = ""
            if task.status == "done":
                output = task.archive_path or task.output_dir
                extra = f" -> {output}" if output is not None else ""
            elif task.status == "failed" and task.error:
                extra = f" -> {task.error}"
            lines.append(f"{task.task_id} [{task.status}] {task.label} by {task.user_name}, {task.elapsed_seconds}s{extra}")
        return "\n".join(lines)

    def cleanup(self) -> int:
        return cleanup_old_files(self.config.download_dir, self.config.cleanup_days) + cleanup_old_files(
            self.config.export_dir,
            self.config.cleanup_days,
        )

    async def _worker_loop(self, index: int) -> None:
        logger.info("jmcomic worker %s started", index)
        while True:
            task, event = await self.queue.get()  # type: ignore[misc]
            try:
                await self._run_task(task, event)
            finally:
                self.queue.task_done()

    async def _run_task(self, task: JmTask, event: Any) -> None:
        if task.status == "cancelled":
            await _emit_text(self.context, event, task.unified_msg_origin, f"任务 {task.task_id} 已在开始前取消。")
            return

        task.status = "running"
        task.started_at = time()
        task.output_dir.mkdir(parents=True, exist_ok=True)
        await _emit_text(self.context, event, task.unified_msg_origin, f"开始下载 {task.label}，任务ID：{task.task_id}")

        try:
            if task.kind == "album":
                await asyncio.to_thread(self.adapter.download_album, task.jm_id, self.config.download_dir)
            else:
                await asyncio.to_thread(self.adapter.download_photo, task.jm_id, self.config.download_dir)

            if not task.output_dir.exists() or not any(task.output_dir.iterdir()):
                fallback_dir = newest_child_dir(self.config.download_dir)
                if fallback_dir is not None:
                    task.output_dir = fallback_dir

            if task.task_id in self.cancelled:
                task.status = "cancelled"
                task.finished_at = time()
                await _emit_text(
                    self.context,
                    event,
                    task.unified_msg_origin,
                    f"任务 {task.task_id} 已完成下载，但此前已被标记为取消，因此不继续发送结果。",
                )
                return

            send_path = task.output_dir
            if self.config.auto_zip:
                task.status = "packing"
                archive = self.config.export_dir / f"{task.output_dir.name}.zip"
                task.archive_path = await asyncio.to_thread(zip_directory, task.output_dir, archive)
                send_path = task.archive_path

            task.status = "sending"
            await self._send_result(event, task, send_path)
            task.status = "done"
            task.finished_at = time()
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            task.finished_at = time()
            logger.error("JM task %s failed: %s", task.task_id, exc, exc_info=exc)
            await _emit_text(self.context, event, task.unified_msg_origin, f"任务 {task.task_id} 失败：{exc}")

    async def _send_result(self, event: Any, task: JmTask, send_path: Path) -> None:
        size = path_size(send_path)
        if is_too_large(send_path, self.config.max_file_size_mb):
            await _emit_text(
                self.context,
                event,
                task.unified_msg_origin,
                f"任务 {task.task_id} 已完成，但输出文件大小为 {size_mb(size)} MB，"
                f"超过限制 {self.config.max_file_size_mb} MB。\n路径：{send_path}",
            )
            return

        if self.config.send_file and send_path.is_file():
            sent = await _emit_file(self.context, event, task.unified_msg_origin, send_path)
            if sent:
                await _emit_text(
                    self.context,
                    event,
                    task.unified_msg_origin,
                    f"任务 {task.task_id} 已完成，文件大小：{size_mb(size)} MB",
                )
                return

        await _emit_text(
            self.context,
            event,
            task.unified_msg_origin,
            f"任务 {task.task_id} 已完成，文件大小：{size_mb(size)} MB\n路径：{send_path}",
        )


def _call_event(event: Any, name: str, default: Any = None) -> Any:
    method = getattr(event, name, None)
    if callable(method):
        try:
            return method()
        except Exception:
            return default
    return default


def _event_obj_attr(event: Any, name: str, default: Any = None) -> Any:
    if hasattr(event, name):
        return getattr(event, name)
    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None and hasattr(message_obj, name):
        return getattr(message_obj, name)
    return default


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _emit_text(context: Any, event: Any, origin: str, text: str) -> bool:
    if await _send_by_context(context, origin, _build_text_chain(text)):
        return True

    for name in ("send", "reply", "send_message"):
        method = getattr(event, name, None)
        if callable(method):
            try:
                await _maybe_await(method(text))
                return True
            except Exception:
                continue
    logger.info("JM task message fallback: %s", text)
    return False


async def _emit_file(context: Any, event: Any, origin: str, path: Path) -> bool:
    try:
        from astrbot.api import message_components as comp

        file_comp = getattr(comp, "File", None)
        if file_comp is None:
            return False
        payload = file_comp(file=str(path), name=path.name)
    except Exception:
        return False

    if await _send_by_context(context, origin, _build_component_chain([payload])):
        return True

    for name in ("send", "reply", "send_message"):
        method = getattr(event, name, None)
        if callable(method):
            try:
                await _maybe_await(method([payload]))
                return True
            except Exception:
                try:
                    await _maybe_await(method(payload))
                    return True
                except Exception:
                    continue
    return False


def _build_text_chain(text: str) -> Any:
    try:
        from astrbot.api.event import MessageChain

        return MessageChain().message(text)
    except Exception:
        return [_plain_component(text)]


def _build_component_chain(components: list[Any]) -> Any:
    try:
        from astrbot.api.event import MessageChain

        chain = MessageChain()
        if hasattr(chain, "chain"):
            chain.chain.extend(components)
        else:
            for component in components:
                chain.append(component)
        return chain
    except Exception:
        return components


def _plain_component(text: str) -> Any:
    try:
        from astrbot.api import message_components as comp

        return comp.Plain(text)
    except Exception:
        return text


async def _send_by_context(context: Any, origin: str, chain: Any) -> bool:
    if not context or not origin:
        return False
    method = getattr(context, "send_message", None)
    if not callable(method):
        return False
    try:
        await _maybe_await(method(origin, chain))
        return True
    except Exception:
        return False
