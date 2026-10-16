"""Refresh only the profile's YouTube block; keep good data during brief outages."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "UCTEwUEqrf_OQ0lV4rbO_Beg"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"
START, END = "<!-- YOUTUBE:START -->", "<!-- YOUTUBE:END -->"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def parse_feed(data):
    root = ET.fromstring(data)
    if root.findtext("yt:channelId", namespaces=NS) != CHANNEL:
        raise ValueError("YouTube feed does not identify the configured channel")
    entries = []
    for entry in root.findall("a:entry", NS):
        video = entry.findtext("yt:videoId", namespaces=NS)
        title = entry.findtext("a:title", namespaces=NS)
        published = entry.findtext("a:published", namespaces=NS)
        if not video or not re.fullmatch(r"[\w-]{11}", video) or not title or not published:
            raise ValueError("YouTube entry is missing valid identity, title or date")
        date = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
        entries.append({"id": video, "title": " ".join(title.split()), "published": date.isoformat()})
    if not entries:
        raise ValueError("YouTube returned no videos; existing list was preserved")
    return sorted({x["id"]: x for x in entries}.values(), key=lambda x: x["published"], reverse=True)[:5]


def replace_block(readme, entries):
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) > readme.index(END):
        raise ValueError("README must have exactly one ordered YouTube marker pair")
    rows = []
    for entry in entries:
        title = html.escape(entry["title"], quote=True)
        rows.append(f'<li><a href="https://www.youtube.com/watch?v={entry["id"]}">{title}</a> <sub>{entry["published"][:10]}</sub></li>')
    content = "\n<ul>\n" + "\n".join(rows) + "\n</ul>\n"
    return readme[:readme.index(START) + len(START)] + content + readme[readme.index(END):]


def fetch_feed(opener=urllib.request.urlopen, sleep=time.sleep):
    error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(FEED, headers={"User-Agent": "Valleytech-profile-feed/1.0", "Accept": "application/atom+xml,application/xml"})
            with opener(request, timeout=20) as response:
                data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError("Unexpectedly large feed")
            return parse_feed(data)
        except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError, ValueError) as exc:
            error = exc
            if attempt < 3:
                sleep((5, 15, 30)[attempt])
    raise RuntimeError("YouTube feed unavailable after four attempts") from error


def cache_fresh(cache, now):
    try:
        checked = dt.datetime.fromisoformat(cache["checked"])
        age = now - checked
        return dt.timedelta() <= age <= dt.timedelta(hours=72) and bool(cache["entries"])
    except (KeyError, TypeError, ValueError):
        return False


def summary(text):
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.write(text + "\n")
    print(text)


def main():
    readme_path, cache_path = ROOT / "README.md", ROOT / "assets/youtube.json"
    original = readme_path.read_text(encoding="utf-8")
    # Check structure before requesting data. Configuration errors must fail.
    replace_block(original, [])
    now = dt.datetime.now(dt.timezone.utc)
    try:
        entries = fetch_feed()
    except RuntimeError:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        if cache_fresh(cache, now):
            summary("YouTube did not return a valid feed after four attempts. Kept the last successful video list; no README or cache files changed. The next scheduled run will retry. Last successful check: " + cache["checked"])
            print("::warning::Temporary YouTube feed outage; last good uploads preserved.")
            return
        summary("YouTube feed has no successful check in the last 72 hours. Existing videos remain unchanged. Check the channel feed and rerun this workflow.")
        raise
    updated = replace_block(original, entries)
    readme_path.write_text(updated, encoding="utf-8")
    cache_path.write_text(json.dumps({"channel": CHANNEL, "checked": now.isoformat(), "entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary(f"Verified the channel feed and refreshed {len(entries)} uploads. This workflow only updates the GitHub profile; it does not publish videos.")


if __name__ == "__main__":
    main()
