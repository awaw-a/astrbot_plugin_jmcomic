from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class PluginConfig:
    enabled: bool = True
    admin_only: bool = False
    allow_group: bool = True

    download_dir: Path = Path("data/jmcomic/downloads")
    export_dir: Path = Path("data/jmcomic/exports")
    option_file: Path = Path("data/jmcomic/option.yml")

    client_impl: str = "api"
    image_suffix: Optional[str] = None
    decode_image: bool = True
    image_threads: int = 30
    photo_threads: Optional[int] = None

    auto_zip: bool = True
    send_file: bool = True
    send_detail_before_download: bool = True
    send_cover: bool = True

    max_concurrent_tasks: int = 1
    max_search_results: int = 8
    max_file_size_mb: int = 200
    cleanup_days: int = 7

    @classmethod
    def load(cls, context: Any = None, base_dir: Optional[Path] = None) -> "PluginConfig":
        base_dir = base_dir or Path(__file__).resolve().parent
        raw = cls._read_context_config(context)
        cfg = cls()

        for key, value in raw.items():
            if not hasattr(cfg, key):
                continue
            if key in {"download_dir", "export_dir", "option_file"}:
                setattr(cfg, key, Path(str(value)))
            else:
                setattr(cfg, key, value)

        cfg.download_dir = cls._abs_path(base_dir, cfg.download_dir)
        cfg.export_dir = cls._abs_path(base_dir, cfg.export_dir)
        cfg.option_file = cls._abs_path(base_dir, cfg.option_file)
        cfg.max_concurrent_tasks = max(1, int(cfg.max_concurrent_tasks))
        cfg.max_search_results = max(1, int(cfg.max_search_results))
        cfg.max_file_size_mb = max(1, int(cfg.max_file_size_mb))
        cfg.ensure_dirs()
        cfg.ensure_option_file()
        return cfg

    @staticmethod
    def _read_context_config(context: Any) -> dict:
        if context is None:
            return {}

        for attr in ("get_config", "get_plugin_config"):
            getter = getattr(context, attr, None)
            if callable(getter):
                try:
                    data = getter()
                    if isinstance(data, dict):
                        return _pick_config_section(data)
                except TypeError:
                    try:
                        data = getter("astrbot_plugin_jmcomic")
                        if isinstance(data, dict):
                            return _pick_config_section(data)
                    except Exception:
                        pass
                except Exception:
                    pass

        data = getattr(context, "config", None)
        return _pick_config_section(data) if isinstance(data, dict) else {}

    @staticmethod
    def _abs_path(base_dir: Path, path: Path) -> Path:
        if path.is_absolute():
            return path
        return (base_dir / path).resolve()

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.option_file.parent.mkdir(parents=True, exist_ok=True)

    def ensure_option_file(self) -> None:
        if self.option_file.exists():
            return

        base_dir = str(self.download_dir).replace("\\", "/")
        suffix_line = "" if self.image_suffix is None else f"    suffix: {self.image_suffix}\n"
        content = (
            "log: true\n\n"
            "dir_rule:\n"
            f"  base_dir: {base_dir}\n"
            "  rule: Bd_Aauthor_Atitle_Pindex\n\n"
            "download:\n"
            "  cache: true\n"
            "  image:\n"
            f"    decode: {str(self.decode_image).lower()}\n"
            f"{suffix_line}"
            "  threading:\n"
            f"    image: {self.image_threads}\n"
            f"    photo: {self.photo_threads or os.cpu_count() or 4}\n\n"
            "client:\n"
            f"  impl: {self.client_impl}\n"
            "  retry_times: 5\n"
        )
        self.option_file.write_text(content, encoding="utf-8")


def _pick_config_section(data: dict) -> dict:
    for key in ("astrbot_plugin_jmcomic", "jmcomic"):
        section = data.get(key)
        if isinstance(section, dict):
            return section
    return data
