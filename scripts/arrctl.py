#!/usr/bin/env python3
"""Compact, credential-safe Sonarr/Radarr operations over SSH.

API keys are read from the Sonarr/Radarr config files on the remote machine;
they are never stored in this script or printed. Configure the config file
locations with --sonarr-config / --radarr-config or the PLEX_SONARR_CONFIG /
PLEX_RADARR_CONFIG environment variables.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


SSH_HELPER = Path(__file__).with_name("plex-ssh.sh")


REMOTE_PROGRAM_TEMPLATE = r'''
import datetime
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVICES = {
    "sonarr": ("http://127.0.0.1:8989/api/v3/", __SONARR_CONFIG__),
    "radarr": ("http://127.0.0.1:7878/api/v3/", __RADARR_CONFIG__),
}

def fail(message, code=2):
    print("ERROR\t" + message, file=sys.stderr)
    raise SystemExit(code)

def service(app):
    if app not in SERVICES:
        fail("app must be sonarr or radarr")
    base, config = SERVICES[app]
    try:
        text = open(config, encoding="utf-8").read()
    except OSError as exc:
        fail("cannot read %s configuration: %s" % (app, exc))
    match = re.search(r"<ApiKey>([^<]+)</ApiKey>", text)
    if not match:
        fail("cannot locate %s API key" % app)
    return base, {"X-Api-Key": match.group(1), "Content-Type": "application/json"}

def api(app, path, method="GET", payload=None, discard=False):
    base, headers = service(app)
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            if discard or not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        fail("%s API returned HTTP %s for %s %s" % (app, exc.code, method, path), 3)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        fail("%s API request failed for %s %s: %s" % (app, method, path, exc), 3)

def records(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.get("records", [])
    return []

def compact(value):
    print(json.dumps(value, separators=(",", ":"), ensure_ascii=True))

def clean(value):
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")

def context(app, query, year):
    roots = api(app, "rootfolder")
    profiles = api(app, "qualityprofile")
    endpoint = "movie" if app == "radarr" else "series"
    matches = []
    if query:
        needle = query.casefold()
        for item in api(app, endpoint):
            if needle not in item.get("title", "").casefold():
                continue
            if year and item.get("year") != year:
                continue
            matches.append({
                "id": item.get("id"), "title": item.get("title"), "year": item.get("year"),
                "qualityProfileId": item.get("qualityProfileId"),
                "rootFolderPath": item.get("rootFolderPath"), "monitored": item.get("monitored"),
                "hasFile": item.get("hasFile") if app == "radarr" else None,
            })
    compact({
        "app": app,
        "roots": [{"path": x.get("path"), "accessible": x.get("accessible"), "freeSpace": x.get("freeSpace")} for x in roots],
        "profiles": [{"id": x.get("id"), "name": x.get("name"), "cutoff": x.get("cutoff"), "upgradeAllowed": x.get("upgradeAllowed")} for x in profiles],
        "matches": matches[:20],
    })

def releases(movie_id, title_filter, limit):
    candidates = api("radarr", "release?" + urllib.parse.urlencode({"movieId": movie_id}))
    needle = title_filter.casefold()
    rows = []
    seen = set()
    for item in candidates:
        title = clean(item.get("title"))
        if needle and needle not in title.casefold():
            continue
        quality = item.get("quality", {}).get("quality", {})
        key = (title, item.get("protocol"), item.get("size"))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "title": title,
            "quality": clean(quality.get("name")),
            "resolution": quality.get("resolution") or 0,
            "sizeGiB": round((item.get("size") or 0) / 1073741824, 2),
            "protocol": clean(item.get("protocol")),
            "approved": bool(item.get("approved")),
            "rejected": bool(item.get("rejected")),
            "customFormatScore": item.get("customFormatScore"),
            "rejections": "; ".join(clean(x) for x in item.get("rejections", [])),
        })
    rows.sort(key=lambda x: (x["approved"], x["resolution"], x["customFormatScore"] or 0, x["protocol"] == "usenet", x["sizeGiB"]), reverse=True)
    print("title\tquality\tresolution\tsizeGiB\tprotocol\tapproved\trejected\tcustomFormatScore\trejections")
    for row in rows[:limit]:
        print("\t".join(clean(row[key]) for key in ("title", "quality", "resolution", "sizeGiB", "protocol", "approved", "rejected", "customFormatScore", "rejections")))
    print("SUMMARY\tshown=%d\tmatched=%d\ttotal=%d" % (min(limit, len(rows)), len(rows), len(candidates)))

def grab(movie_id, protocol, exact_title, allow_rejected):
    candidates = api("radarr", "release?" + urllib.parse.urlencode({"movieId": movie_id}))
    matches = [x for x in candidates if x.get("title") == exact_title and x.get("protocol") == protocol]
    if not matches:
        fail("no exact %s release match for %s" % (protocol, exact_title), 4)
    matches.sort(key=lambda x: (bool(x.get("approved")), x.get("customFormatScore") or 0), reverse=True)
    selected = matches[0]
    if (selected.get("rejected") or not selected.get("approved")) and not allow_rejected:
        reasons = "; ".join(clean(x) for x in selected.get("rejections", [])) or "candidate is not approved"
        fail("release is rejected; explicit --allow-rejected required: " + reasons, 4)
    api("radarr", "release", "POST", selected, discard=True)
    quality = selected.get("quality", {}).get("quality", {}).get("name")
    print("GRABBED\t%s\t%s\t%s\t%.2f GiB" % (clean(exact_title), clean(protocol), clean(quality), (selected.get("size") or 0) / 1073741824))

def status(app, item_id):
    endpoint = "movie" if app == "radarr" else "series"
    item = api(app, "%s/%d" % (endpoint, item_id))
    queue_data = api(app, "queue?" + urllib.parse.urlencode({"page": 1, "pageSize": 200, "includeUnknownSeriesItems": "true"}))
    queue = []
    for row in records(queue_data):
        if row.get("movieId" if app == "radarr" else "seriesId") != item_id:
            continue
        queue.append({k: row.get(k) for k in ("title", "status", "trackedDownloadStatus", "protocol", "size", "sizeleft", "timeleft")})
    command_data = api(app, "command?includeCompleted=true")
    commands = []
    for row in records(command_data):
        body = row.get("body", {})
        related = item_id in body.get("movieIds", []) if app == "radarr" else body.get("seriesId") == item_id
        if related:
            commands.append({k: row.get(k) for k in ("id", "name", "status", "queued", "started", "ended", "message")})
    commands = commands[-5:]
    result = {"app": app, "id": item_id, "title": item.get("title"), "year": item.get("year"), "queue": queue, "commands": commands}
    if app == "radarr":
        movie_file = item.get("movieFile") or {}
        result.update({"hasFile": bool(item.get("hasFile")), "filePath": movie_file.get("path"), "sizeOnDisk": item.get("sizeOnDisk")})
        result["state"] = "imported" if result["hasFile"] else ("downloading" if queue else "added")
    else:
        episodes = api("sonarr", "episode?" + urllib.parse.urlencode({"seriesId": item_id}))
        monitored = [x for x in episodes if x.get("monitored")]
        files = [x for x in monitored if x.get("hasFile")]
        result.update({"monitoredEpisodes": len(monitored), "episodesWithFiles": len(files), "missingMonitoredEpisodes": len(monitored) - len(files)})
        result["state"] = "downloading" if queue else ("imported" if monitored and len(files) == len(monitored) else ("partially-imported" if files else "added"))
    compact(result)

def season_only(tvdb_id, season_number, profile_id, root_path, execute, search, replace_monitoring):
    lookup = api("sonarr", "series/lookup?" + urllib.parse.urlencode({"term": "tvdb:%d" % tvdb_id}))
    match = next((x for x in lookup if x.get("tvdbId") == tvdb_id), None)
    if not match:
        fail("no Sonarr lookup match for TVDB id %d" % tvdb_id, 4)
    existing = next((x for x in api("sonarr", "series") if x.get("tvdbId") == tvdb_id), None)
    profiles = api("sonarr", "qualityprofile")
    roots = api("sonarr", "rootfolder")
    if not any(x.get("id") == profile_id for x in profiles):
        fail("quality profile id %d does not exist" % profile_id, 4)
    if not any(x.get("path") == root_path for x in roots):
        fail("root path does not exist: %s" % root_path, 4)
    if not any(x.get("seasonNumber") == season_number for x in match.get("seasons", [])):
        fail("season %d is not present in the Sonarr lookup result" % season_number, 4)
    plan = {"title": match.get("title"), "year": match.get("year"), "tvdbId": tvdb_id, "season": season_number, "qualityProfileId": profile_id, "rootFolderPath": root_path, "existingSeriesId": existing.get("id") if existing else None, "search": search}
    if not execute:
        plan["state"] = "plan-only"
        compact(plan)
        return
    if existing and not replace_monitoring:
        fail("series already exists; --replace-monitoring is required to change its monitoring scope", 4)
    if existing:
        series = existing
    else:
        match.update({"qualityProfileId": profile_id, "rootFolderPath": root_path, "monitored": False, "addOptions": {"searchForMissingEpisodes": False, "searchForCutoffUnmetEpisodes": False}})
        for season in match.get("seasons", []):
            season["monitored"] = False
        series = api("sonarr", "series", "POST", match)
    series["qualityProfileId"] = profile_id
    series["rootFolderPath"] = root_path
    series["monitored"] = True
    for season in series.get("seasons", []):
        season["monitored"] = season.get("seasonNumber") == season_number
    series = api("sonarr", "series/%d" % series["id"], "PUT", series)
    episodes = api("sonarr", "episode?" + urllib.parse.urlencode({"seriesId": series["id"]}))
    target_ids = [x["id"] for x in episodes if x.get("seasonNumber") == season_number]
    other_ids = [x["id"] for x in episodes if x.get("seasonNumber") != season_number]
    if other_ids:
        api("sonarr", "episode/monitor", "PUT", {"episodeIds": other_ids, "monitored": False}, discard=True)
    if target_ids:
        api("sonarr", "episode/monitor", "PUT", {"episodeIds": target_ids, "monitored": True}, discard=True)
    command_id = None
    if search:
        today = datetime.datetime.now(datetime.timezone.utc)
        search_ids = []
        for episode in episodes:
            if episode.get("id") not in target_ids or episode.get("hasFile"):
                continue
            air = episode.get("airDateUtc")
            if air:
                try:
                    aired = datetime.datetime.fromisoformat(air.replace("Z", "+00:00")) <= today
                except ValueError:
                    aired = False
                if aired:
                    search_ids.append(episode["id"])
        if search_ids:
            command = api("sonarr", "command", "POST", {"name": "EpisodeSearch", "episodeIds": search_ids})
            command_id = command.get("id")
    queue_data = api("sonarr", "queue?" + urllib.parse.urlencode({"page": 1, "pageSize": 200, "includeUnknownSeriesItems": "true"}))
    out_of_scope = []
    for row in records(queue_data):
        if row.get("seriesId") == series["id"] and row.get("episodeId") not in target_ids:
            out_of_scope.append({"id": row.get("id"), "title": clean(row.get("title")), "status": row.get("status")})
    compact({**plan, "state": "configured", "seriesId": series["id"], "targetEpisodeCount": len(target_ids), "commandId": command_id, "outOfScopeQueue": out_of_scope})

try:
    invocation = json.loads(base64.urlsafe_b64decode(sys.argv[1]).decode())
except (IndexError, ValueError, json.JSONDecodeError) as exc:
    fail("invalid encoded invocation: %s" % exc)
action = invocation[0]
args = invocation[1:]
if action == "context":
    context(args[0], args[1], int(args[2]) if args[2] else None)
elif action == "releases":
    releases(int(args[0]), args[1], int(args[2]))
elif action == "grab":
    grab(int(args[0]), args[1], args[2], args[3] == "true")
elif action == "status":
    status(args[0], int(args[1]))
elif action == "season-only":
    season_only(int(args[0]), int(args[1]), int(args[2]), args[3], args[4] == "true", args[5] == "true", args[6] == "true")
else:
    fail("unknown action")
'''


def run_remote(action: str, arguments: tuple, sonarr_config: str, radarr_config: str) -> int:
    if not SSH_HELPER.is_file():
        print(f"SSH helper is missing: {SSH_HELPER}", file=sys.stderr)
        return 2
    remote_program = REMOTE_PROGRAM_TEMPLATE.replace(
        "__SONARR_CONFIG__", json.dumps(sonarr_config)
    ).replace(
        "__RADARR_CONFIG__", json.dumps(radarr_config)
    )
    invocation = [action, *(str(x) for x in arguments)]
    payload = base64.urlsafe_b64encode(json.dumps(invocation).encode()).decode()
    command = [str(SSH_HELPER), "python3", "-", payload]
    result = subprocess.run(command, input=remote_program, text=True, check=False)
    return result.returncode


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Compact, credential-safe Sonarr/Radarr operations over SSH")
    root.add_argument("--sonarr-config", default=os.environ.get("PLEX_SONARR_CONFIG"),
                      help="path to Sonarr config.xml on the remote machine (or set PLEX_SONARR_CONFIG)")
    root.add_argument("--radarr-config", default=os.environ.get("PLEX_RADARR_CONFIG"),
                      help="path to Radarr config.xml on the remote machine (or set PLEX_RADARR_CONFIG)")
    commands = root.add_subparsers(dest="command", required=True)

    context_parser = commands.add_parser("context", help="show compact roots, profiles, and existing-title matches")
    context_parser.add_argument("app", choices=("sonarr", "radarr"))
    context_parser.add_argument("--query", default="")
    context_parser.add_argument("--year", type=int)

    release_parser = commands.add_parser("releases", help="list sanitized Radarr release candidates")
    release_parser.add_argument("movie_id", type=int)
    release_parser.add_argument("--filter", default="")
    release_parser.add_argument("--limit", type=int, choices=range(1, 101), default=20, metavar="1-100")

    grab_parser = commands.add_parser("grab", help="grab one exact Radarr release; mutating")
    grab_parser.add_argument("movie_id", type=int)
    grab_parser.add_argument("protocol", choices=("usenet", "torrent"))
    grab_parser.add_argument("exact_title")
    grab_parser.add_argument("--allow-rejected", action="store_true")

    status_parser = commands.add_parser("status", help="show compact queue, command, and import status")
    status_parser.add_argument("app", choices=("sonarr", "radarr"))
    status_parser.add_argument("item_id", type=int)

    season_parser = commands.add_parser("season-only", help="plan or configure an exact Sonarr season; mutating with --execute")
    season_parser.add_argument("tvdb_id", type=int)
    season_parser.add_argument("season", type=int)
    season_parser.add_argument("profile_id", type=int)
    season_parser.add_argument("root_path")
    season_parser.add_argument("--execute", action="store_true")
    season_parser.add_argument("--search", action="store_true")
    season_parser.add_argument("--replace-monitoring", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    for app, config in (("sonarr", args.sonarr_config), ("radarr", args.radarr_config)):
        if not config:
            print(f"Missing --{app}-config (or PLEX_{app.upper()}_CONFIG). "
                  f"Set it to the path of {app}'s config.xml on the remote machine.", file=sys.stderr)
            return 2
    remote = lambda action, *a: run_remote(action, a, args.sonarr_config, args.radarr_config)
    if args.command == "context":
        return remote("context", args.app, args.query, args.year or "")
    if args.command == "releases":
        return remote("releases", args.movie_id, args.filter, args.limit)
    if args.command == "grab":
        return remote("grab", args.movie_id, args.protocol, args.exact_title, str(args.allow_rejected).lower())
    if args.command == "status":
        return remote("status", args.app, args.item_id)
    return remote("season-only", args.tvdb_id, args.season, args.profile_id, args.root_path, str(args.execute).lower(), str(args.search).lower(), str(args.replace_monitoring).lower())


if __name__ == "__main__":
    raise SystemExit(main())
