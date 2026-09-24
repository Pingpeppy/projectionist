#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if (( $# < 1 )); then
  echo "Usage: $0 <command> [key=value ...]" >&2
  exit 2
fi

command_name="$1"
shift

if [[ ! "$command_name" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "Invalid Tautulli command name" >&2
  exit 2
fi

for argument in "$@"; do
  if [[ ! "$argument" =~ ^[A-Za-z0-9_]+= ]]; then
    echo "Invalid parameter; expected key=value: $argument" >&2
    exit 2
  fi
done

tautulli_config="${PLEX_TAUTULLI_CONFIG:-}"
if [[ -z "$tautulli_config" ]]; then
  echo "PLEX_TAUTULLI_CONFIG is not set. Set it to the path of Tautulli's config.ini on the remote machine." >&2
  exit 2
fi

# Forward the config path to the remote shell (quoted safely).
"$SCRIPT_DIR/plex-ssh.sh" "PLEX_TAUTULLI_CONFIG=$(printf '%q' "$tautulli_config") bash -s -- $(printf '%q ' "$command_name" "$@")" <<'REMOTE' | python3 -m json.tool
set -euo pipefail

command_name="$1"
shift
config_file="${PLEX_TAUTULLI_CONFIG:?PLEX_TAUTULLI_CONFIG was not forwarded}"

api_key="$(sed -n -E 's/^[[:space:]]*api_key[[:space:]]*=[[:space:]]*([^[:space:]]+).*/\1/p' "$config_file" | head -n 1)"
if [[ -z "$api_key" ]]; then
  echo 'Could not read the Tautulli API key' >&2
  exit 3
fi

curl_args=(
  --fail
  --silent
  --show-error
  --max-time 15
  --get
  'http://127.0.0.1:8181/api/v2'
  --data-urlencode "apikey=$api_key"
  --data-urlencode "cmd=$command_name"
)

for argument in "$@"; do
  curl_args+=(--data-urlencode "$argument")
done

curl "${curl_args[@]}"
REMOTE
