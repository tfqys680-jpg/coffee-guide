#!/usr/bin/env python3
"""Validate the single-page sitemap against an explicit content review (stdlib only)."""

import argparse
from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
URL = "https://7story.co.jp/"
REVIEW = "seo/content-review.json"
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class CanonicalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.urls.append(attrs.get("href"))


def content_hash(root):
    # Include filenames as well as bytes: additions/deletions/renames are changes.
    # Intentionally conservative: CSS/JS/copyright edits also require a review,
    # but the reviewer can retain lastmod for non-significant changes.
    paths = [root / "index.html", root / "hero-slides.json"]
    paths += [p for p in (root / "assets").rglob("*") if p.is_file()]
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def validate(root, today=None, base=None):
    today = today or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    review = json.loads((root / REVIEW).read_text())
    lastmod = review["lastmod"]
    if not isinstance(lastmod, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod):
        raise ValueError("lastmod must be a YYYY-MM-DD date")
    if date.fromisoformat(lastmod) > today:
        raise ValueError("lastmod must not be in the future (Asia/Tokyo)")
    if review["change_type"] not in ("significant", "non-significant"):
        raise ValueError("change_type must be significant or non-significant")
    if not review["reason"].strip():
        raise ValueError("A content-review reason is required")
    if review["url"] != URL:
        raise ValueError("Review URL must be the canonical apex URL")
    if review["content_sha256"] != content_hash(root):
        raise ValueError("Public content changed without a matching review. See docs/sitemap.md")
    # Adding pages needs an explicit sitemap design update, not silent omission.
    if {p.name for p in root.glob("*.html")} != {"index.html"}:
        raise ValueError("New root HTML page: extend sitemap coverage and this validator")

    tree = ET.parse(root / "sitemap.xml").getroot()
    if tree.tag != NS + "urlset" or len(tree) != 1 or tree[0].tag != NS + "url":
        raise ValueError("Expected one sitemap URL with the sitemap XML namespace")
    entry = tree[0]
    if len(entry.findall(NS + "loc")) != 1 or entry.findtext(NS + "loc") != URL:
        raise ValueError("Sitemap must contain the canonical apex URL exactly once")
    if len(entry.findall(NS + "lastmod")) != 1 or entry.findtext(NS + "lastmod") != lastmod:
        raise ValueError("Sitemap lastmod does not match the content review")
    parser = CanonicalParser()
    parser.feed((root / "index.html").read_text())
    if parser.urls != [URL]:
        raise ValueError("HTML canonical must remain the single apex URL")
    robots = (root / "robots.txt").read_text().splitlines()
    sitemap_lines = [s.strip() for s in robots if s.lower().startswith("sitemap:")]
    if sitemap_lines != ["Sitemap: " + URL + "sitemap.xml"]:
        raise ValueError("robots.txt sitemap URL differs from the canonical site")

    if base:
        # The initial PR has no baseline review; only that case is skipped.
        tracked = subprocess.check_output(
            ["git", "ls-tree", "--name-only", base, "--", REVIEW], cwd=root, text=True
        ).strip()
        if tracked:
            previous = json.loads(subprocess.check_output(
                ["git", "show", f"{base}:{REVIEW}"], cwd=root, text=True
            ))
            if lastmod < previous["lastmod"]:
                raise ValueError("lastmod must not move backwards")
            if review["content_sha256"] != previous["content_sha256"]:
                if review["reason"].strip() == previous["reason"].strip():
                    raise ValueError("Changed content requires a new review reason")
                if review["change_type"] == "non-significant" and lastmod != previous["lastmod"]:
                    raise ValueError("Non-significant changes must retain lastmod")
    return lastmod


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="PR base commit/ref for review-decision checks")
    parser.add_argument("--print-content-hash", action="store_true")
    args = parser.parse_args()
    try:
        if args.print_content_hash:
            print(content_hash(ROOT))
        else:
            print(f"PASS: sitemap lastmod={validate(ROOT, base=args.base)}")
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
