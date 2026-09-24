# Projectionist

An AI-agent skill for safely managing a home Plex Media Server, the
Sonarr/Radarr acquisition stack, and Tautulli analytics — over SSH, with no
exposed ports.

This is not another MCP server binary. The servers already exist
([plex-mcp-server](https://github.com/tdabasinskas/plex-mcp-server),
[ARR-MCP](https://github.com/gauranshmathur/arr_mcp), and others cover that
ground well). This repo is the **operations layer** on top: a written skill
file that teaches an AI agent how to run your media stack without breaking
it, plus the small, credential-safe helpers the skill calls.

## What it does

An agent using this skill can, in plain language:

- "What's on the server? What haven't I watched?"
- "Download season 4 of *Animal Control*" — added season-only, monitored
  exactly that season, searched for missing aired episodes.
- "What's downloading right now? Is anything stuck?"
- "Free up space — what's the biggest stuff I haven't watched?"
- "Who's streaming, and what are they watching?"
- Container health checks, log reads, library scans, trash emptying.

## Architecture

```
Your laptop / agent host
        │  SSH (keypair), ideally over Tailscale
        ▼
Media server (Docker)
 ├── plex-mcp container  →  Plex MCP server, stdio transport
 ├── plex                  →  Plex Media Server (:32400, localhost)
 ├── sonarr / radarr       →  *Arr stack (:8989 / :7878, localhost)
 └── tautulli              →  analytics (:8181, localhost)
```

Key design decisions:

1. **No exposed HTTP.** The agent reaches the Plex MCP server via
   `docker exec ... --transport stdio` over SSH. Nothing listens on the
   network for the agent; there is no Cloudflare Tunnel, no OAuth gateway,
   no forwarded port.
2. **Credentials never leave the server.** Sonarr/Radarr API keys are read
   from their own `config.xml` files on the server at call time. Tautulli's
   key is read from its `config.ini`. Nothing is stored in this repo, in
   agent memory, or in chat.
3. **Sanitized outputs.** Release candidates from indexers can contain API
   keys in their URLs, so the helpers emit bounded, redacted tables — never
   raw JSON.
4. **Written safety doctrine.** `SKILL.md` encodes authorization tiers
   (read-only first, confirm before destructive or library-wide actions),
   a verification vocabulary (Added ≠ Queued ≠ Imported ≠ Available in
   Plex), and the season-only discipline for TV additions, so the agent
   can't "helpfully" download an entire series.

## Quickstart

1. On your media server: Docker running Plex, Sonarr, Radarr, Tautulli, and
   a Plex MCP server container (any MCP-compatible one that supports the
   stdio transport).
2. Install Tailscale on both machines and note the server's tailnet IP or
   MagicDNS name. (Plain LAN SSH works too; Tailscale is recommended.)
3. Create a dedicated SSH keypair and add the public key to the server.
4. Copy `.env.example` to `.env` (or export the variables) and fill in:
   `PLEX_SSH_HOST`, `PLEX_SSH_USER`, `PLEX_SSH_KEY`, plus the config-file
   paths for Sonarr/Radarr/Tautulli.
5. Verify: `scripts/status.sh` and
   `scripts/mcp-stdio.py tools/call '{"name":"server_info","arguments":{}}'`.
6. Point your agent at this repo as a skill (Claude Code, Codex, and other
   skill-aware agents) or paste `SKILL.md` into its instructions.

## Layout

```
SKILL.md                 The agent skill: setup, tool choice, authorization,
                         secret hygiene, verification vocabulary.
scripts/
  plex-ssh.sh            Single SSH entry point; everything uses this.
  mcp-stdio.py           MCP JSON-RPC client over SSH stdio.
  arrctl.py              Compact Sonarr/Radarr ops: context, releases, grab,
                         status, season-only adds. Credential-safe.
  tautulli.sh            Tautulli API wrapper (key read remotely).
  status.sh              Container health snapshot.
references/
  server.md              Stack facts, ports, TRaSH profile invariants.
  tautulli-api.md        Tautulli API notes.
.env.example             All configuration in one place.
```

## Safety model

- **Read-only by default.** The skill requires resolving the exact target
  with read-only calls before any change.
- **Confirmation gates** on deletion, trash emptying, library-wide
  scans/searches, config edits, service lifecycle actions, and playback
  control.
- **Scoped requests stay scoped.** A request about one title never
  authorizes adjacent titles or library-wide migrations.
- **Truthful status.** The agent reports only the highest state it
  verified — it will not tell you something is "in Plex" when it has only
  been queued for download.

## License

MIT. See [LICENSE](LICENSE).
