# astrbot_plugin_jmcomic

这是一个基于 `JMComic-Crawler-Python` 的 AstrBot 插件，支持在聊天中查询、搜索和下载 JMComic 内容，并提供后台队列、自动压缩、文件大小限制和旧文件清理。

## 功能

- 后台下载，不阻塞 AstrBot 主事件循环。
- 支持下载整本 album 或单个章节/photo。
- 支持查询本子详情和搜索本子。
- 支持下载完成后自动打包为 zip。
- 支持文件发送；如果当前平台不支持文件消息，会回退为返回本地文件路径。
- 支持任务队列、任务取消和旧文件清理。
- 内置 `JMComic-Crawler-Python`，无需额外拉取子仓库。

## 指令

- `/jm <album_id>`：加入整本下载任务。
- `/jmp <photo_id>`：加入单章节下载任务。
- `/jm_info <album_id>`：只查看本子详情，不下载。
- `/jm_search <关键词>`：搜索本子并返回前几条结果。
- `/jm_queue`：查看最近的下载任务。
- `/jm_cancel <任务ID>`：取消排队中的任务，或标记运行中的任务为取消。
- `/jm_clean`：清理过期的下载和导出文件。
- `/jm_files [显示数量]`：查看当前系统保存的下载和导出文件。
- `/jm_test_push`：测试当前会话是否支持下载完成后的主动推送。

## 配置

插件提供了 `_conf_schema.json`，安装后可以在 AstrBot WebUI 的插件配置界面中直接修改配置。配置会由 AstrBot 保存到对应的插件配置文件中，并在插件启动时传入。

可配置字段如下：

```yaml
jmcomic:
  enabled: true
  admin_only: false
  allow_group: true
  download_dir: data/jmcomic/downloads
  export_dir: data/jmcomic/exports
  option_file: data/jmcomic/option.yml
  client_impl: api
  image_suffix:
  decode_image: true
  image_threads: 30
  photo_threads:
  auto_zip: true
  send_file: true
  send_detail_before_download: true
  send_cover: true
  max_concurrent_tasks: 1
  max_search_results: 8
  max_file_size_mb: 200
  cleanup_days: 1
```

`option_file` 仍然是标准的 `jmcomic` 配置文件。插件首次启动时会自动创建一份最小可用配置，并在运行时用 AstrBot 插件配置覆盖常用字段，例如下载目录、客户端类型、并发数、图片后缀等。

默认保存规则会以 album_id 作为目录名，导出的 zip 也会命名为 `{album_id}.zip`。例如 `JM123456` 会保存到 `downloads/123456/`，导出为 `exports/123456.zip`。

## 依赖

插件依赖已写入 `requirements.txt`。如果 AstrBot 没有自动安装依赖，可在插件目录执行：

```bash
python -m pip install -r requirements.txt
```

## 许可说明

本 AstrBot 插件主体遵循根目录 `LICENSE`。

`JMComic-Crawler-Python/` 是内置的第三方源码，来源于 `https://github.com/hect0x7/JMComic-Crawler-Python`，保留其上游 MIT License。详见 `THIRD_PARTY_NOTICES.md` 和 `JMComic-Crawler-Python/LICENSE`。
