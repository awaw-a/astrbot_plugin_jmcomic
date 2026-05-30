# astrbot_plugin_jmcomic

基于 `JMComic-Crawler-Python` 的 AstrBot 插件，支持在聊天中查询、搜索和下载 JMComic 内容，并提供后台队列、自动压缩、压缩包密码、文件清理和保存文件查看。

## 功能

- 后台下载，不阻塞 AstrBot 主事件循环。
- 支持下载整本 album 或单个章节/photo。
- 支持查询本子详情和搜索本子。
- 下载完成后可自动打包为 zip。
- 默认启用 zip 密码，默认密码为 `123`，可在 WebUI 修改或关闭。
- 可选择 zip 成功后删除原始下载目录，只保留压缩包。
- 支持任务队列、任务取消、保存文件查看和旧文件清理。
- 内置 `JMComic-Crawler-Python`，无需额外拉取子仓库。

## 指令

- `/jm <album_id>`：加入整本下载任务。
- `/jmp <photo_id>`：加入单章节下载任务。
- `/jm_info <album_id>`：只查看本子详情，不下载。
- `/jm_search <关键词>`：搜索本子并返回前几条结果。
- `/jm_queue`：查看最近的下载任务。
- `/jm_cancel <任务ID>`：取消排队中的任务，或标记运行中的任务为取消。
- `/jm_files [显示数量]`：查看当前保存的下载目录和导出文件。
- `/jm_clean`：清理过期的下载和导出文件。
- `/jm_test_push`：测试当前会话是否支持下载完成后的主动推送。
- `/jm_help`：查看所有可用指令，并显示当前压缩包密码状态。

如果输入未知的 `/jm...` 指令，bot 会提示使用 `/jm_help` 查看帮助。

## 保存规则

默认以 `album_id` 作为保存名：

```text
downloads/{album_id}/
exports/{album_id}.zip
```

例如 `JM350234` 会保存到：

```text
data/jmcomic/downloads/350234/
data/jmcomic/exports/350234.zip
```

如果开启 `delete_source_after_zip`，zip 成功生成后会删除 `downloads/{album_id}/`，只保留 `exports/{album_id}.zip`。

## 配置

插件提供 `_conf_schema.json`，安装后可以在 AstrBot WebUI 的插件配置界面中直接修改配置。

主要配置项如下：

```yaml
enabled: true
admin_only: false
allow_group: true
download_dir: data/jmcomic/downloads
export_dir: data/jmcomic/exports
option_file: data/jmcomic/option.yml
client_impl: api
image_suffix: ""
decode_image: true
image_threads: 30
photo_threads: 0
auto_zip: true
delete_source_after_zip: false
zip_password_enabled: true
zip_password: "123"
send_file: true
send_detail_before_download: true
send_cover: true
max_concurrent_tasks: 1
max_search_results: 8
max_file_size_mb: 200
cleanup_days: 1
```

说明：

- `photo_threads: 0` 表示使用系统 CPU 核心数。
- `image_suffix` 留空表示使用原图后缀；可填 `.jpg`、`.png`、`.webp`。
- `cleanup_days` 默认是 `1`，`/jm_clean` 会清理早于该天数的下载和导出文件。
- `option_file` 仍然是标准 `jmcomic` 配置文件。插件会在运行时强制使用 `Bd_Aid` 保存规则，因此旧配置文件里的目录规则不会影响 album_id 保存名。

## 文件发送说明

插件会尝试通过 AstrBot 的文件消息发送 zip。如果当前 QQ/OneBot 实现不支持文件发送，或者协议端无法读取插件生成的本地文件，可能会出现“看到文件消息但无法下载”的情况。

可用以下方式排查：

- 使用 `/jm_test_push` 测试当前会话是否支持主动推送。
- 使用 `/jm_files` 查看 zip 是否已经生成并仍然存在。
- 使用 `/jm_queue` 查看任务状态、完成路径或失败原因。
- 如果 AstrBot 和 OneBot/NapCat/Lagrange 不在同一个容器，需要确认协议端能读取 `exports` 下的 zip 文件路径。

**注意：若压缩包未开启密码，QQ很可能会检测到违规内容，导致无法下载。**

## 依赖

插件依赖已写入 `requirements.txt`。如果 AstrBot 没有自动安装依赖，可在插件目录执行：

```bash
python -m pip install -r requirements.txt
```

加密 zip 依赖 `pyzipper`。如果开启 `zip_password_enabled` 但未安装依赖，下载任务会提示安装依赖。

## 许可说明

本 AstrBot 插件主体遵循根目录 `LICENSE`。

`JMComic-Crawler-Python/` 是内置的第三方源码，来源于 `https://github.com/hect0x7/JMComic-Crawler-Python`，保留其上游 MIT License。详见 `THIRD_PARTY_NOTICES.md` 和 `JMComic-Crawler-Python/LICENSE`。
