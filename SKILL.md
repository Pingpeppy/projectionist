---
name: plex-manage
description: Safely inspect and manage a home Plex Media Server, Tautulli analytics, and Sonarr/Radarr stack over SSH. Use for the server's health, libraries, media, sessions, history, containers, downloads, or acquisition services.
---

# Plex management over SSH

Manage a live home media stack: Plex Media Server plus the Sonarr/Radarr
acquisition stack and Tautulli analytics. This is not a sandbox. Every command
in this skill runs against the real server.

## Setup

All connections go through `scripts/plex-ssh.sh`. Configure it once with
environment variables:

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `PLEX_SSH_HOST` | yes | — | Hostname or IP of the media server |
| `PLEX_SSH_USER` | no | `$USER` | SSH user on the media server |
| `PLEX_SSH_PORT` | no | `22` | SSH port |
| `PLEX_SSH_KEY` | no | ssh default | Dedicated private key for this connection |

Other configuration:

| Variable | Used by | Meaning |
|---|---|---|
| `PLEX_SONARR_CONFIG` | `arrctl.py` | Path to Sonarr `config.xml` on the server |
| `PLEX_RADARR_CONFIG` | `arrctl.py` | Path to Radarr `config.xml` on the server |
| `PLEX_TAUTULLI_CONFIG` | `tautulli.sh` | Path to Tautulli `config.ini` on the server |
| `PLEX_MCP_CONTAINER` | `mcp-stdio.py` | Docker container of the Plex MCP server (`plex-mcp`) |
| `PLEX_MCP_BINARY` | `mcp-stdio.py` | MCP server binary in the container (`plex-mcp-server`) |

See `.env.example`. Reaching the server over Tailscale (tailnet IP or
MagicDNS name) is strongly recommended. Never expose the server publicly,
forward router ports to it, or use Funnel-style public tunnels for it.

## Choose the shortest safe tool path

1. For Plex, use the MCP server over SSH stdio:

   ```bash
   scripts/mcp-stdio.py tools/list
   scripts/mcp-stdio.py tools/call '{"name": "<tool>", "arguments": {...}}'
   ```

   This runs the MCP server inside its container on the media server and speaks
   MCP JSON-RPC over the SSH session. No Plex ports are exposed.

2. For ordinary Sonarr/Radarr lookups, additions, searches, queues, and
   calendars, prefer the bundled compact helper over ad-hoc raw API commands:

   ```bash
   scripts/arrctl.py --help
   ```

   It reads API keys from the servers' own config files and never prints them.

3. For host, Docker, logs, files, or advanced raw APIs, use `scripts/plex-ssh.sh`:

   ```bash
   scripts/plex-ssh.sh '<remote command>'
   ```

4. For watch history and analytics, use `scripts/tautulli.sh`; it reads the key
   remotely and never prints it.

Read [references/server.md](references/server.md) for stack facts, port layout,
and quality-profile invariants before host/container work or raw API changes.
Read [references/tautulli-api.md](references/tautulli-api.md) for Tautulli work.

## Authorization and scope

- Resolve the exact target with read-only calls before changing live state.
- An explicit request to download an exact title and year authorizes its ordinary
  Arr addition and title-scoped search. Reconfirm only if the match is ambiguous,
  movie/series/season scope is unclear, the requested fallback materially changes,
  a rejected release must be overridden, configuration must change, or the action
  is destructive or library-wide.
- Before an addition, resolve the title/year, root folder, quality profile, and
  monitoring/search behavior. Resolve profile and root names dynamically; do not
  assume saved numeric IDs are current.
- A title-scoped or requested-season search is ordinary. Confirm immediately
  before a full-series backlog search not explicitly requested, a library-wide
  search/scan, deletion, trash emptying, service/container lifecycle action,
  configuration edit, arbitrary SQL, or active-client control.
- For one Sonarr season, add unmonitored, enable only the requested season and
  its episodes, then search only that season's missing aired episode IDs. Never
  add with `monitored: true`. Use `arrctl.py season-only`; it refuses to replace
  monitoring on an existing series without `--replace-monitoring`.
- A request concerning one title, season, file, or queue entry never authorizes
  adjacent titles or a library-wide migration.

## Secret and output safety

- Never print, log, return, or pretty-print raw Sonarr/Radarr release objects.
  They can contain indexer API keys in URLs. Extract only title, quality,
  resolution, size, protocol, approval/custom-format state, and rejection
  reasons; suppress mutation response bodies.
- Never expose Plex, Sonarr, Radarr, Tautulli, indexer, or download-client
  tokens in chat or terminal output. Avoid unredacted configuration,
  environment, `docker inspect`, release, and download-client responses.
- Do not use `grep` on raw release JSON. Use `arrctl.py releases`, which emits a
  bounded sanitized table.
- Do not assume `jq` exists on the server. Prefer bundled helpers; for an
  unsupported raw operation, send a small standalone Python program and emit
  only selected fields.

## Verification vocabulary

Report only the highest state actually verified:

- **Added**: present in Sonarr/Radarr.
- **Queued/downloading**: accepted by a download client.
- **Imported**: Arr reports `hasFile` and a destination file.
- **Available in Plex**: Plex returns the item after import/scan.

Submission is not completion. Use `arrctl.py status` to check command, queue,
and import state; once imported, verify Plex visibility via the MCP server.
Keep output scoped to the requested title and avoid dumping whole queues or
libraries.

## Fixed infrastructure safeguards

- Never infer that a container or process is a duplicate. Verify network mode,
  ports, compose labels, and role first.
- Plex MCP container: launch with `docker exec -i <container> <binary>
  --transport stdio` over SSH. Do not register a legacy SSE endpoint as
  streamable HTTP.
- If Sonarr/Radarr run through a VPN container, their localhost API ports are
  still the way in; the VPN only affects outbound download traffic.

For overall container health, run `scripts/status.sh`.
