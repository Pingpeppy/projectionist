# Media-stack reference

Facts about the Docker media stack this skill manages. Adjust the paths below
to match your own compose project; the ports are the applications' defaults.

## Access

- All access goes through `scripts/plex-ssh.sh`. Configure `PLEX_SSH_HOST`,
  `PLEX_SSH_USER`, `PLEX_SSH_PORT`, and `PLEX_SSH_KEY` once; every helper uses it.
- Reaching the server over Tailscale (tailnet IP or MagicDNS name) is strongly
  recommended. Do not expose SSH, Plex, or the *Arrs to the public internet,
  and do not use port forwarding or tunnels that bypass your tailnet.

## Layout (defaults; change to match your setup)

- Compose project: `~/docker/torrent-stack/docker-compose.yml` (example path)
- Plex: single `plex` container, host networking. Host-visible Plex processes
  are not evidence of a duplicate native installation.
- Plex HTTP: `127.0.0.1:32400` on the server (localhost only).
- Plex MCP: `plex-mcp` container (`$PLEX_MCP_CONTAINER`); launch over SSH stdio:
  `docker exec -i plex-mcp plex-mcp-server --transport stdio`.
  Do not use the legacy SSE endpoint even if one is listening.
- Tautulli: `tautulli` container, HTTP on `127.0.0.1:8181`.
- Sonarr: `sonarr` container, HTTP on `127.0.0.1:8989` (host port).
- Radarr: `radarr` container, HTTP on `127.0.0.1:7878` (host port).

## *Arr notes

- Sonarr/Radarr API keys live in their `config.xml` files on the server.
  `scripts/arrctl.py` reads them remotely; they are never stored locally or
  printed. Point `--sonarr-config` / `--radarr-config` (or `PLEX_SONARR_CONFIG`
  / `PLEX_RADARR_CONFIG`) at those files.
- Sonarr/Radarr may run through a VPN container (e.g. Gluetun). The *Arr APIs
  are still reached at the localhost ports above; the VPN only affects their
  outbound download traffic.
- Do not assume `jq` exists on the server.

## Quality-profile invariants (TRaSH guides)

If you follow the TRaSH guides, your Sonarr/Radarr profiles likely contain
intentional "junk" filters. Know them before you touch profiles:

- Very negative custom-format scores (e.g. `-10000` for LQ, Upscaled, AV1,
  BR-DISK, Extras, Bad Dual Groups) are usually deliberate.
- A softened `Language: Not Original` score (e.g. `-50` with a matching
  `minFormatScore`) is often intentional so anime/fansub releases are not
  universally rejected. Do not "fix" it back to a hard block.
- A delay profile that prefers Usenet immediately and delays torrents (e.g. 60
  minutes) with `bypassIfHighestQuality` enabled is usually intentional.

When in doubt, read the profile before changing it; these scores look like
mistakes but are load-bearing.

## Safe read-only checks

```bash
scripts/plex-ssh.sh "docker ps --filter name=plex --filter name=tautulli --filter name=sonarr --filter name=radarr --filter name=gluetun --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'"
scripts/plex-ssh.sh "docker logs --tail 100 plex"
```

Avoid unredacted `docker inspect`, application configuration dumps, release
responses, and download-client responses in chat or logs. Container
environments and release URLs can contain credentials.
