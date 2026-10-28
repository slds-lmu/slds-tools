#!/usr/bin/env bash
# Print the page tree below a page, or of a whole space, as a Markdown list.
#
# Usage: ./page-tree.sh <root-page-id | space-key>
#   One line per page: linked title, page ID, version, date + author of last edit.
#   No page contents.
# Writes to stdout; save with e.g. `> <pages-dir>/page-tree_<root>.md`.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

[[ $# -eq 1 ]] || { echo "usage: page-tree.sh <root-page-id | space-key>" >&2; exit 2; }
ROOT="$1"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

EXPAND="ancestors,version,extensions.position"
if [[ "$ROOT" =~ ^[0-9]+$ ]]; then
  conf_curl "$CONF_BASE/rest/api/content/$ROOT?expand=$EXPAND" > "$TMP_DIR/root.json"
  # The /descendant/page endpoint currently does not work on BayernCollab.
  LIST_URL="$CONF_BASE/rest/api/content/search?cql=type%3Dpage%20and%20ancestor%3D$ROOT&expand=$EXPAND"
else
  LIST_URL="$CONF_BASE/rest/api/space/$ROOT/content/page?depth=all&expand=$EXPAND"
fi

# One request per batch of pages; the API's `_links.next` signals more.
LIMIT=200
start=0
while :; do
  batch_file="$TMP_DIR/batch-$(printf '%05d' "$start").json"
  conf_curl "$LIST_URL&limit=$LIMIT&start=$start" > "$batch_file"
  python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get("_links", {}).get("next") else 1)' \
    "$batch_file" || break
  start=$((start + LIMIT))
done

python3 - "$TMP_DIR" "$ROOT" "$CONF_BASE" <<'PY'
import sys, json, os, glob
from collections import defaultdict
from datetime import datetime
tmp_dir, root, base = sys.argv[1:4]

def load(path):
    d = json.load(open(path))
    if d.get("statusCode"):
        sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")
    return d

pages = {}
for batch in sorted(glob.glob(os.path.join(tmp_dir, "batch-*.json"))):
    for p in load(batch)["results"]:
        pages[p["id"]] = p

root_page = None
if os.path.exists(os.path.join(tmp_dir, "root.json")):
    root_page = load(os.path.join(tmp_dir, "root.json"))
    pages[root_page["id"]] = root_page

children = defaultdict(list)
for p in pages.values():
    if root_page and p["id"] == root_page["id"]:
        continue
    parent = p["ancestors"][-1]["id"] if p.get("ancestors") else None
    children[parent].append(p)

def position(p):
    # Manually ordered pages carry a position; unordered ones sort by title.
    pos = (p.get("extensions") or {}).get("position")
    return (pos if isinstance(pos, int) else 10**9, p["title"].lower())

def line(p, depth):
    v = p["version"]
    title = p["title"].replace("[", r"\[").replace("]", r"\]")
    by = (v.get("by") or {}).get("displayName", "?")
    return (f"{'  ' * depth}- [{title}]({base}{p['_links']['webui']}) — "
            f"`{p['id']}` · v{v['number']} · {v['when'][:10]} {by}")

out = []
def walk(p, depth):
    out.append(line(p, depth))
    for child in sorted(children[p["id"]], key=position):
        walk(child, depth + 1)

if root_page:
    heading = f'Page tree below "{root_page["title"]}" (`{root_page["id"]}`)'
    walk(root_page, 0)
else:
    heading = f"Page tree of space `{root}`"
    for top in sorted(children[None], key=position):
        walk(top, 0)

print(f"# {heading}\n")
print(f"_Generated {datetime.now().astimezone().isoformat(timespec='minutes')} by page-tree.sh; "
      f"{len(pages)} pages. Format: title — ID · version · last edit._\n")
print("\n".join(out))
PY
