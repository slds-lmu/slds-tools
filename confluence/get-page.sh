#!/usr/bin/env bash
# Fetch a Confluence page's storage-format body to three local files.
#
# Usage: ./get-page.sh -d <pages-dir> [-x <exclude-file>] [-f] <page-id>
#   Writes, in <pages-dir>:
#     <id>_<title>.xhtml         working copy — for editing
#     <id>_<title>.pulled.xhtml  untouched copy as pulled (for diff / revert)
#     <id>_<title>.meta.json     version + pull time (used for version control)
#   -x  pages in the exclude file and their subpages are excluded
#   -f  overwrite a working copy that has local edits
# Prints the page title, current version and last edit to stderr.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

usage() { echo "usage: get-page.sh -d <pages-dir> [-x <exclude-file>] [-f] <page-id>" >&2; exit 2; }
PAGES_DIR="" EXCLUDE_FILE="" FORCE=0
while getopts "d:x:f" opt; do
  case "$opt" in
    d) PAGES_DIR="$OPTARG" ;;
    x) EXCLUDE_FILE="$OPTARG" ;;
    f) FORCE=1 ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ -n "$PAGES_DIR" && $# -eq 1 ]] || usage
PAGE_ID="$1"
EXCLUDED="$(conf_excluded_ids "$EXCLUDE_FILE")"
mkdir -p "$PAGES_DIR"

JSON_FILE="$(mktemp)"
trap 'rm -f "$JSON_FILE"' EXIT

conf_curl "$CONF_BASE/rest/api/content/$PAGE_ID?expand=body.storage,version,space,ancestors" > "$JSON_FILE"

python3 - "$PAGES_DIR" "$PAGE_ID" "$JSON_FILE" "$FORCE" "$EXCLUDED" "$CONF_BASE" <<'PY'
import sys, json, re, os, glob
from datetime import datetime
pages_dir, page_id, json_file, force, excluded, base = sys.argv[1:7]
d = json.load(open(json_file))
if d.get("statusCode"):
    sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")

ancestors = d.get("ancestors", [])
chain = {a["id"] for a in ancestors} | {d["id"]}
if chain & set(filter(None, excluded.split(","))):
    sys.exit(f"REFUSING: page {page_id} is excluded (or below an excluded page).")

def read(path):
    with open(path) as f:
        return f.read()

# Files are found by ID, not name: a title change on the server renames them.
for old_meta in glob.glob(os.path.join(glob.escape(pages_dir), f"{page_id}_*.meta.json")):
    old_base = old_meta[: -len(".meta.json")]
    work, pulled = old_base + ".xhtml", old_base + ".pulled.xhtml"
    has_local_edits = os.path.exists(work) and (
        not os.path.exists(pulled) or read(work) != read(pulled))
    if has_local_edits and force != "1":
        sys.exit(f"REFUSING: {work} has local edits (diff it against the .pulled copy; -f overwrites).")
    for path in (work, pulled, old_meta):
        if os.path.exists(path):
            os.remove(path)

slug = re.sub(r"\W+", "-", d["title"]).strip("-")[:60]
out_base = os.path.join(pages_dir, f"{page_id}_{slug}")
ver = d["version"]
author = ver.get("by", {})
meta = {
    "id": d["id"],
    "title": d["title"],
    "space": d["space"]["key"],
    "url": base + d["_links"]["webui"],
    "ancestors": [{"id": a["id"], "title": a["title"]} for a in ancestors],
    "version": ver["number"],
    "version_when": ver["when"],
    "version_by": author.get("displayName"),
    "version_by_username": author.get("username"),
    "version_message": ver.get("message", ""),
    "pulled_at": datetime.now().astimezone().isoformat(timespec="seconds"),
}
body = d["body"]["storage"]["value"]
for suffix in (".xhtml", ".pulled.xhtml"):
    with open(out_base + suffix, "w") as f:
        f.write(body)
with open(out_base + ".meta.json", "w") as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)
    f.write("\n")
sys.stderr.write(f'Saved "{d["title"]}" v{ver["number"]} (last edit {ver["when"]} '
                 f'by {meta["version_by"]}) -> {out_base}.xhtml\n')
PY
