#!/usr/bin/env bash
# SSH helper for the plex-manage skill.
#
# Opens an SSH session to the machine hosting your Plex / *Arr stack and runs
# the given remote command. All other scripts in this skill call this helper,
# so configuring your connection here configures everything.
#
# Configuration (environment variables):
#   PLEX_SSH_HOST   (required)  Hostname or IP of your media server.
#                               A Tailscale IP or MagicDNS name is recommended;
#                               never expose this machine to the public internet.
#   PLEX_SSH_USER   (optional)  SSH user. Defaults to your local username.
#   PLEX_SSH_PORT   (optional)  SSH port. Defaults to 22.
#   PLEX_SSH_KEY    (optional)  Path to the private key for this connection.
#                               Use a dedicated keypair and keep it scoped to
#                               this host. If unset, ssh uses its default keys.
#
# Example:
#   export PLEX_SSH_HOST=100.64.0.10      # Tailscale IP of the media server
#   export PLEX_SSH_USER=media
#   export PLEX_SSH_KEY=~/.ssh/plex_manage
set -euo pipefail

host="${PLEX_SSH_HOST:-}"
if [[ -z "$host" ]]; then
  echo "PLEX_SSH_HOST is not set. Set it to the hostname or IP of your media server." >&2
  exit 2
fi

user="${PLEX_SSH_USER:-$USER}"
port="${PLEX_SSH_PORT:-22}"

ssh_args=(
  -o BatchMode=yes
  -o ConnectTimeout=15
  -o StrictHostKeyChecking=accept-new
  -p "$port"
)

if [[ -n "${PLEX_SSH_KEY:-}" ]]; then
  if [[ ! -r "$PLEX_SSH_KEY" ]]; then
    echo "PLEX_SSH_KEY is not readable: $PLEX_SSH_KEY" >&2
    exit 2
  fi
  ssh_args+=(-i "$PLEX_SSH_KEY")
fi

exec ssh "${ssh_args[@]}" "${user}@${host}" "$@"
