from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path


def zip_directory(src_dir: Path, dest_zip: Path) -> Path:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
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
