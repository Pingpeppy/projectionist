# Tautulli API reference

Run commands through `../scripts/tautulli.sh`. The helper connects to the media server over SSH (see `PLEX_SSH_HOST` and friends), reads Tautulli's API key from its config file on the server, queries `127.0.0.1:8181`, and pretty-prints JSON. Do not put the API key in a command, skill file, or response.

## Read-only commands

| Command | Useful parameters | Purpose |
|---|---|---|
| `get_activity` | `session_key`, `session_id` | Active streams and transcode detail |
| `get_history` | `user`, `media_type`, `after`, `before`, `length` | Playback history |
| `get_home_stats` | `time_range`, `stats_type`, `stat_id`, `stats_count` | Popular content/users/platforms |
| `get_libraries` | — | Libraries and summary statistics |
| `get_library` | `section_id` | One library |
| `get_library_watch_time_stats` | `section_id`, `query_days` | Library watch time |
| `get_recently_added` | `count`, `media_type`, `section_id` | Recently added content |
| `get_users` | — | Users with access |
| `get_user_watch_time_stats` | `user_id`, `query_days` | Per-user watch time |
| `search` | `query`, `limit` | Search cached Plex content |
| `get_metadata` | `rating_key` | Metadata for an item |
| `get_stream_data` | `row_id` or `session_key` | Stream detail |
| `get_server_info` | — | Server identity and state |

## Mutating commands

Require explicit confirmation immediately before any `delete_*`, `edit_*`, `set_*`, `notify*`, `restart`, `backup_*`, `import_*`, `logout_user_session`, or `sql` command. `sql` is arbitrary database access and needs the exact intended query and effect confirmed.

For the server's current authoritative command documentation, use `tautulli.sh docs_md`; inspect it without copying secrets into the conversation.
