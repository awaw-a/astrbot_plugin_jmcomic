from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

try:
    from .models import SearchItem
    from .plugin_config import PluginConfig
except ImportError:
    from models import SearchItem
    from plugin_config import PluginConfig


class JmcomicAdapter:
    def __init__(self, config: PluginConfig, root_dir: Path):
        self.config = config
        self.root_dir = root_dir
        self.jmcomic = self._import_jmcomic()

    def _import_jmcomic(self):
        src = self.root_dir / "JMComic-Crawler-Python" / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import jmcomic

        return jmcomic

    def parse_jm_id(self, text: str) -> str:
        return self.jmcomic.JmcomicText.parse_to_jm_id(text.strip())

    def build_option(self, base_dir: Optional[Path] = None):
        jmcomic = self.jmcomic
        if self.config.option_file.exists():
            option = jmcomic.create_option_by_file(str(self.config.option_file))
        else:
            option = jmcomic.JmOption.default()

        if base_dir is not None:
            option.dir_rule.base_dir = str(base_dir)
        else:
            option.dir_rule.base_dir = str(self.config.download_dir)
        option.dir_rule = self.jmcomic.DirRule("Bd_Aid", base_dir=option.dir_rule.base_dir)

        option.client.impl = self.config.client_impl
        option.download.image.decode = self.config.decode_image
        option.download.threading.image = self.config.image_threads
        if self.config.photo_threads is not None:
            option.download.threading.photo = self.config.photo_threads
        if self.config.image_suffix:
            option.download.image.suffix = self._fix_suffix(self.config.image_suffix)
        return option

    def get_album_info(self, album_id: str):
        option = self.build_option()
        client = option.new_jm_client()
        return client.get_album_detail(album_id)

    def get_cover_url(self, album_id: str) -> str:
        return self.jmcomic.JmcomicText.get_album_cover_url(album_id)

    def format_album_info(self, album: Any) -> str:
        tags = self._join_limited(getattr(album, "tags", []), 12)
        authors = self._join_limited(getattr(album, "authors", []), 6) or getattr(album, "author", "")
        lines = [
            f"JM{album.album_id}",
            f"Title: {album.name}",
            f"Author: {authors or 'unknown'}",
            f"Chapters: {len(album)}",
            f"Pages: {album.page_count}",
            f"Views: {album.views}",
            f"Likes: {album.likes}",
        ]
        if tags:
            lines.append(f"Tags: {tags}")
        if self.config.send_cover:
            lines.append(f"Cover: {self.get_cover_url(album.album_id)}")
        return "\n".join(lines)

    def search(self, keyword: str, limit: int) -> list[SearchItem]:
        option = self.build_option()
        client = option.new_jm_client()
        page = client.search_site(keyword)
        items: list[SearchItem] = []
        for album_id, info in page[:limit]:
            items.append(
                SearchItem(
                    album_id=str(album_id),
                    title=str(info.get("name", "")),
                    tags=list(info.get("tags", []) or []),
                )
            )
        return items

    def download_album(self, album_id: str, task_dir: Path):
        option = self.build_option(task_dir)
        return self.jmcomic.download_album(album_id, option)

    def download_photo(self, photo_id: str, task_dir: Path):
        option = self.build_option(task_dir)
        return self.jmcomic.download_photo(photo_id, option)

    @staticmethod
    def _fix_suffix(suffix: str) -> str:
        suffix = suffix.strip()
        return suffix if suffix.startswith(".") else f".{suffix}"

    @staticmethod
    def _join_limited(items: list[str], limit: int) -> str:
        if not items:
            return ""
        shown = [str(x) for x in items[:limit]]
        suffix = "" if len(items) <= limit else f" ... +{len(items) - limit}"
        return ", ".join(shown) + suffix
