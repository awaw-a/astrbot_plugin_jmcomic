# astrbot_plugin_jmcomic

AstrBot plugin wrapper for `JMComic-Crawler-Python`.

## Commands

- `/jm <album_id>`: queue an album download.
- `/jmp <photo_id>`: queue a single chapter/photo download.
- `/jm_info <album_id>`: show album detail without downloading.
- `/jm_search <keyword>`: search albums and show the first results.
- `/jm_queue`: show recent tasks.
- `/jm_cancel <task_id>`: cancel a queued task, or mark a running task as cancelled.
- `/jm_clean`: remove old download/export outputs.

## Behavior

Downloads run in background workers so AstrBot is not blocked. Finished outputs are zipped when `auto_zip` is enabled. The plugin tries to send the zip file if the current AstrBot adapter supports file messages; otherwise it returns the local path.

## Config

The plugin works with defaults. If your AstrBot environment exposes plugin config as a dict, these keys are supported:

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
  cleanup_days: 7
```

`option_file` is still a normal `jmcomic` option file. The plugin creates a minimal one on first start, then overrides the most common runtime fields from the AstrBot config.
