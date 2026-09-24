#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/plex-ssh.sh" \
  "docker ps --filter name=plex --filter name=tautulli --filter name=sonarr --filter name=radarr --filter name=gluetun --format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
