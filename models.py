from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import Literal, Optional
from uuid import uuid4


TaskKind = Literal["album", "photo"]
TaskStatus = Literal[
    "queued",
    "running",
    "packing",
    "sending",
    "done",
    "failed",
    "cancelled",
]


@dataclass
class JmTask:
    kind: TaskKind
    jm_id: str
    user_id: str
    user_name: str
    session_id: str
    unified_msg_origin: str = ""
    task_id: str = field(default_factory=lambda: uuid4().hex[:8])
    status: TaskStatus = "queued"
    created_at: float = field(default_factory=time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    output_dir: Optional[Path] = None
    archive_path: Optional[Path] = None

    @property
    def label(self) -> str:
        prefix = "JM" if self.kind == "album" else "PHOTO"
        return f"{prefix}{self.jm_id}"

    @property
    def elapsed_seconds(self) -> int:
        end = self.finished_at or time()
        start = self.started_at or self.created_at
        return max(0, int(end - start))


@dataclass
class SearchItem:
    album_id: str
    title: str
    tags: list[str]
