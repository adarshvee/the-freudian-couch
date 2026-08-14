#!/usr/bin/env python3
"""
migrate_blogger_images.py
=========================

Localize Blogger-hosted images so the site stops depending on
blogger.googleusercontent.com / *.bp.blogspot.com.

WHAT IT DOES (deliberately the low-risk approach)
-------------------------------------------------
  * Downloads each Blogger *image* into   static/images/blogger/<post-slug>/<file>
  * Rewrites the Blogger URL inside the post to an absolute site path:
        https://blogger.googleusercontent.com/.../file.jpg  ->  /images/blogger/<slug>/file.jpg
  * Post files are NOT moved, renamed, or converted to page bundles.
    -> Permalinks are untouched. Raw <img src="/images/..."> works from any
       page URL, including the .html "ugly URLs" these Blogger posts use.
  * It ONLY touches image hosts (blogger.googleusercontent.com and
    *.bp.blogspot.com). Plain blogspot.com *article links* are left alone.
  * Thumbnails are OUT OF SCOPE (handled separately). This script is only
    about killing the Blogger image dependency.

Everything is reversible with git. This script never runs git and never pushes.

MODES
-----
  audit    (default) READ-ONLY. Scan posts, probe every Blogger image URL for
           reachability, write a report. Makes no changes, downloads nothing
           except tiny HEAD/range probes.
  migrate  Download images and rewrite posts. Honors --dry-run.
  verify   READ-ONLY post-migration checks: no Blogger image URLs remain in the
           targeted posts, and every /images/blogger/... reference exists on
           disk. With --build, also runs `hugo` and checks it succeeds.

SCOPE CONTROL (use these to pilot before batching)
  --only <slug>    operate on a single post, e.g.
                   --only kurt-vonneguts-slaughterhouse-five
  --limit <n>      operate on at most n posts

TYPICAL SIGN-OFF FLOW
  1) python3 scripts/migrate_blogger_images.py audit
        -> review scripts/blogger_audit_report.md (dead links, sizes, plan)
  2) python3 scripts/migrate_blogger_images.py migrate --only <slug> --dry-run
        -> review exactly what it would download/rewrite
  3) python3 scripts/migrate_blogger_images.py migrate --only <slug>
  4) python3 scripts/migrate_blogger_images.py verify --only <slug> --build
  5) eyeball the post on your running hugo server, then git diff / commit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# --- Paths (repo root is the parent of this scripts/ dir) --------------------
ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content" / "posts"
STATIC_IMG_DIR = ROOT / "static" / "images" / "blogger"
REPORT_MD = ROOT / "scripts" / "blogger_audit_report.md"
MANIFEST_JSON = ROOT / "scripts" / "blogger_migrate_manifest.json"

# --- What counts as a Blogger *image* URL ------------------------------------
# Only these hosts are image CDNs. Plain blogspot.com article links are ignored
# on purpose so we never rewrite a link to another post as if it were an image.
IMAGE_HOST_RE = re.compile(
    r"^(blogger\.googleusercontent\.com|(\w+\.)?bp\.blogspot\.com)$", re.I
)
# A guard so we only grab things that actually look like images.
IMAGE_LIKE_RE = re.compile(
    r"(\.(jpe?g|png|gif|webp|bmp)(\?|$))|(/s\d+(-c)?/)|(=s\d+)|(/w\d+-h\d+)", re.I
)
# Any absolute http(s) URL, stopping at quotes/space/paren/angle brackets.
URL_RE = re.compile(r"""https?://[^\s"'()<>\\]+""", re.I)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 30


# --- Small helpers -----------------------------------------------------------
def post_slug(md_path: Path) -> str:
    """Slug for a post: parent dir for bundles (index.md), else the file stem."""
    if md_path.name == "index.md":
        return md_path.parent.name
    return md_path.stem


def find_posts(only: str | None, limit: int | None) -> list[Path]:
    posts = sorted(p for p in CONTENT_DIR.rglob("*.md"))
    if only:
        posts = [p for p in posts if post_slug(p) == only]
        if not posts:
            sys.exit(f"ERROR: no post matched --only {only!r}")
    if limit is not None:
        posts = posts[:limit]
    return posts


def is_blogger_image(url: str) -> bool:
    try:
        host = urlparse(url).netloc.split("@")[-1].split(":")[0]
    except ValueError:
        return False
    return bool(IMAGE_HOST_RE.match(host)) and bool(IMAGE_LIKE_RE.search(url))


def extract_image_urls(text: str) -> list[str]:
    """Ordered, de-duplicated Blogger image URLs found in the text."""
    seen: dict[str, None] = {}
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,);\"'")  # trim trailing punctuation
        if is_blogger_image(u) and u not in seen:
            seen[u] = None
    return list(seen)


def other_blogspot_links(text: str) -> list[str]:
    """Non-image blogspot links we intentionally leave alone (for the report)."""
    out = []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,);\"'")
        host = urlparse(u).netloc.lower()
        if "blogspot.com" in host and not is_blogger_image(u):
            out.append(u)
    return sorted(set(out))


def local_filename(url: str, content_type: str | None = None) -> str:
    """Deterministic, collision-free local filename for a URL."""
    path = urlparse(url).path
    base = path.rsplit("/", 1)[-1] or "image"
    stem, ext = os.path.splitext(base)
    if not ext:
        ext = mimetypes.guess_extension(content_type or "") or ".jpg"
        if ext == ".jpe":
            ext = ".jpg"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "image"
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"{stem}__{digest}{ext.lower()}"


def probe(url: str) -> dict:
    """Reachability probe: HEAD, falling back to a 1-byte ranged GET."""
    def _try(method: str, headers: dict) -> dict:
        req = Request(url, method=method, headers=headers)
        with urlopen(req, timeout=TIMEOUT) as r:
            return {
                "ok": True,
                "status": r.status,
                "content_type": r.headers.get("Content-Type"),
                "length": r.headers.get("Content-Length"),
            }

    base = {"User-Agent": USER_AGENT}
    try:
        return _try("HEAD", base)
    except HTTPError as e:
        if e.code in (403, 405, 501):  # HEAD sometimes disallowed
            try:
                return _try("GET", {**base, "Range": "bytes=0-0"})
            except Exception as e2:  # noqa: BLE001
                return {"ok": False, "status": getattr(e2, "code", None), "error": str(e2)}
        return {"ok": False, "status": e.code, "error": str(e)}
    except (URLError, Exception) as e:  # noqa: BLE001
        return {"ok": False, "status": None, "error": str(e)}


def download(url: str, dest: Path) -> tuple[bool, str]:
    """Download url -> dest. Returns (ok, message)."""
    if dest.exists() and dest.stat().st_size > 0:
        return True, f"skip (exists, {dest.stat().st_size} bytes)"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            data = r.read()
        if not data:
            return False, "empty response"
        if ctype and not ctype.lower().startswith("image/"):
            return False, f"not an image (Content-Type: {ctype})"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True, f"downloaded {len(data)} bytes"
    except Exception as e:  # noqa: BLE001
        return False, f"ERROR: {e}"


# --- Modes -------------------------------------------------------------------
def cmd_audit(posts: list[Path], do_probe: bool) -> None:
    rows = []
    total_imgs = 0
    dead = 0
    for p in posts:
        text = p.read_text(encoding="utf-8")
        urls = extract_image_urls(text)
        if not urls:
            continue
        total_imgs += len(urls)
        entries = []
        for u in urls:
            info = {"url": u, "local": local_filename(u)}
            if do_probe:
                pr = probe(u)
                info["reachable"] = pr.get("ok", False)
                info["status"] = pr.get("status")
                info["content_type"] = pr.get("content_type")
                info["length"] = pr.get("length")
                if not pr.get("ok"):
                    dead += 1
                time.sleep(0.05)  # be polite to the CDN
            entries.append(info)
        rows.append(
            {
                "slug": post_slug(p),
                "file": str(p.relative_to(ROOT)),
                "image_count": len(urls),
                "images": entries,
                "skipped_blogspot_links": other_blogspot_links(text),
            }
        )

    # Machine-readable + human-readable outputs
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "scripts" / "blogger_audit.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )

    lines = ["# Blogger image audit", ""]
    lines.append(f"- Posts with Blogger images: **{len(rows)}**")
    lines.append(f"- Total Blogger image URLs: **{total_imgs}**")
    if do_probe:
        lines.append(f"- Unreachable (dead) images: **{dead}**")
    lines.append("")
    for r in rows:
        lines.append(f"## {r['slug']}  ({r['image_count']} images)")
        lines.append(f"`{r['file']}`")
        lines.append("")
        for e in r["images"]:
            status = ""
            if do_probe:
                mark = "OK" if e.get("reachable") else "DEAD"
                status = f" — **{mark}** (HTTP {e.get('status')}, {e.get('content_type')}, {e.get('length')} bytes)"
            lines.append(f"- `{e['local']}`{status}")
            lines.append(f"  - src: {e['url']}")
        if r["skipped_blogspot_links"]:
            lines.append("")
            lines.append("  _Non-image blogspot links left untouched:_")
            for lnk in r["skipped_blogspot_links"]:
                lines.append(f"  - {lnk}")
        lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Posts with Blogger images : {len(rows)}")
    print(f"Total Blogger image URLs  : {total_imgs}")
    if do_probe:
        print(f"Unreachable images        : {dead}")
    print(f"\nReport : {REPORT_MD.relative_to(ROOT)}")
    print(f"JSON   : scripts/blogger_audit.json")
    if do_probe and dead:
        print("\nWARNING: some images are unreachable. Review the report before migrating.")


def cmd_migrate(posts: list[Path], dry_run: bool) -> None:
    manifest = {}
    n_posts = n_imgs = n_fail = 0
    for p in posts:
        text = p.read_text(encoding="utf-8")
        urls = extract_image_urls(text)
        if not urls:
            continue
        slug = post_slug(p)
        dest_dir = STATIC_IMG_DIR / slug
        new_text = text
        post_map = {}
        print(f"\n[{slug}]  {len(urls)} image(s)")
        for u in urls:
            fname = local_filename(u)
            dest = dest_dir / fname
            web_path = f"/images/blogger/{slug}/{fname}"
            if dry_run:
                print(f"  would download -> static/images/blogger/{slug}/{fname}")
                print(f"  would rewrite  -> {web_path}")
            else:
                ok, msg = download(u, dest)
                print(f"  {fname}: {msg}")
                if not ok:
                    n_fail += 1
                    print(f"  !! keeping original URL for this one (download failed)")
                    continue
            new_text = new_text.replace(u, web_path)
            post_map[u] = web_path
            n_imgs += 1
        if not dry_run and post_map:
            p.write_text(new_text, encoding="utf-8")
            manifest[slug] = {"file": str(p.relative_to(ROOT)), "map": post_map}
        n_posts += 1

    if not dry_run:
        existing = {}
        if MANIFEST_JSON.exists():
            existing = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        existing.update(manifest)
        MANIFEST_JSON.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print(f"\n{'DRY RUN — ' if dry_run else ''}posts: {n_posts}, images: {n_imgs}, failures: {n_fail}")
    if not dry_run:
        print(f"Manifest: {MANIFEST_JSON.relative_to(ROOT)}")
        print("Next: run `verify`, then eyeball the post and `git diff`.")


def cmd_verify(posts: list[Path], do_build: bool) -> None:
    problems = []
    remaining = 0
    checked_refs = 0
    for p in posts:
        text = p.read_text(encoding="utf-8")
        left = extract_image_urls(text)
        if left:
            remaining += len(left)
            problems.append(f"{post_slug(p)}: {len(left)} Blogger image URL(s) still present")
        for m in re.finditer(r"/images/blogger/[^\s\"')<>]+", text):
            ref = m.group(0)
            fpath = ROOT / "static" / ref.lstrip("/").replace("images/blogger", "images/blogger", 1)
            checked_refs += 1
            if not fpath.exists():
                problems.append(f"{post_slug(p)}: missing local file for {ref}")

    print(f"Local /images/blogger refs checked : {checked_refs}")
    print(f"Blogger image URLs still present   : {remaining}")

    if do_build:
        print("\nRunning hugo build ...")
        r = subprocess.run(
            ["hugo", "--quiet", "--baseURL", "https://www.thefreudiancouch.com/"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode != 0:
            problems.append(f"hugo build failed:\n{r.stderr.strip()}")
        else:
            print("hugo build: OK")

    if problems:
        print("\nVERIFY FAILED:")
        for pr in problems:
            print(f"  - {pr}")
        sys.exit(1)
    print("\nVERIFY PASSED ✅")


# --- CLI ---------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", default="audit", choices=["audit", "migrate", "verify"])
    ap.add_argument("--only", help="operate on a single post slug")
    ap.add_argument("--limit", type=int, help="operate on at most N posts")
    ap.add_argument("--dry-run", action="store_true", help="(migrate) plan only, no downloads/writes")
    ap.add_argument("--no-probe", action="store_true", help="(audit) skip network reachability checks")
    ap.add_argument("--build", action="store_true", help="(verify) also run hugo build")
    args = ap.parse_args()

    if not CONTENT_DIR.is_dir():
        sys.exit(f"ERROR: {CONTENT_DIR} not found — run from the repo root.")

    posts = find_posts(args.only, args.limit)
    print(f"Mode: {args.mode} | posts in scope: {len(posts)}"
          f"{' | only=' + args.only if args.only else ''}\n")

    if args.mode == "audit":
        cmd_audit(posts, do_probe=not args.no_probe)
    elif args.mode == "migrate":
        cmd_migrate(posts, dry_run=args.dry_run)
    elif args.mode == "verify":
        cmd_verify(posts, do_build=args.build)


if __name__ == "__main__":
    main()
