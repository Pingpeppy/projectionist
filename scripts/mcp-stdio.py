#!/usr/bin/env python3
"""Call a method on a Plex MCP server over SSH stdio.

Runs the MCP server inside its Docker container on the media server
(via scripts/plex-ssh.sh), performs the MCP initialize handshake, issues the
requested method, and prints the result as JSON.

Usage:
    mcp-stdio.py <method> [params-json]

Examples:
    mcp-stdio.py tools/list
    mcp-stdio.py tools/call '{"name": "library_list", "arguments": {}}'

Configuration (environment variables):
    PLEX_MCP_CONTAINER  Docker container running the MCP server (default: plex-mcp)
    PLEX_MCP_BINARY     MCP server binary inside the container (default: plex-mcp-server)
Plus whatever scripts/plex-ssh.sh needs (PLEX_SSH_HOST, ...).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SSH_HELPER = str(Path(__file__).with_name("plex-ssh.sh"))
CONTAINER = os.environ.get("PLEX_MCP_CONTAINER", "plex-mcp")
BINARY = os.environ.get("PLEX_MCP_BINARY", "plex-mcp-server")
REMOTE_CMD = ["docker", "exec", "-i", CONTAINER, BINARY, "--transport", "stdio"]


def rpc(proc: subprocess.Popen, method: str, params=None, req_id: int = 1) -> dict:
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP server closed the pipe unexpectedly")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip log lines or partial output
        if obj.get("id") == req_id:
            return obj
        # otherwise: a server notification; keep waiting for our response


def main() -> None:
    method = sys.argv[1] if len(sys.argv) > 1 else "tools/list"
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None

    proc = subprocess.Popen(
        [SSH_HELPER] + REMOTE_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        init = rpc(
            proc,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "plex-manage-skill", "version": "1.0"},
            },
        )
        if "error" in init:
            print(json.dumps(init, indent=2))
            sys.exit(1)
        # initialized notification (no id, no response expected)
        proc.stdin.write(
            (json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode()
        )
        proc.stdin.flush()

        result = rpc(proc, method, params, req_id=2)
        if "error" in result:
            print(json.dumps(result["error"], indent=2))
            sys.exit(1)
        print(json.dumps(result.get("result", result), indent=2))
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
