from __future__ import annotations

import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def zip_directory(src_dir: Path, dest_zip: Path, password: str | None = None) -> Path:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    if password:
        try:
            import pyzipper
        except ImportError as exc:
            raise RuntimeError("启用压缩包密码需要安装 pyzipper，请先安装 requirements.txt 中的依赖。") from exc

        with pyzipper.AESZipFile(
            dest_zip,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zipf:
            zipf.setpassword(password.encode("utf-8"))
            for path in src_dir.rglob("*"):
                if path.is_file():
                    zipf.write(path, path.relative_to(src_dir))
        return dest_zip

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in src_dir.rglob("*"):
            if path.is_file():
                zipf.write(path, path.relative_to(src_dir))
    return dest_zip


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def size_mb(size: int) -> float:
    return round(size / 1024 / 1024, 2)


def is_too_large(path: Path, limit_mb: int) -> bool:
    return path_size(path) > limit_mb * 1024 * 1024


def cleanup_old_files(root: Path, days: int) -> int:
    if days <= 0 or not root.exists():
        return 0

    cutoff = time.time() - days * 24 * 60 * 60
    removed = 0
    for item in root.iterdir():
        try:
            if item.stat().st_mtime >= cutoff:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except FileNotFoundError:
            continue
    return removed


@dataclass
class SavedPathInfo:
    path: Path
    root: Path
    is_dir: bool
    size: int
    mtime: float

    @property
    def relative_name(self) -> str:
        try:
            return str(self.path.relative_to(self.root))
        except ValueError:
            return self.path.name

    @property
    def modified_text(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")


def list_saved_items(roots: list[Path], limit: int = 30) -> tuple[list[SavedPathInfo], int, int]:
    items: list[SavedPathInfo] = []
    total_size = 0
    total_count = 0

    for root in roots:
        if not root.exists():
            continue
        for path in root.iterdir():
            try:
                stat = path.stat()
                size = path_size(path)
            except FileNotFoundError:
                continue
            total_count += 1
            total_size += size
            items.append(
                SavedPathInfo(
                    path=path,
                    root=root,
                    is_dir=path.is_dir(),
                    size=size,
                    mtime=stat.st_mtime,
                )
            )

    items.sort(key=lambda item: item.mtime, reverse=True)
    return items[:limit], total_count, total_size


def newest_child_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    dirs = [item for item in root.iterdir() if item.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda item: item.stat().st_mtime)
