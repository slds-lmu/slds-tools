#!/usr/bin/env bash
# Full-text search over Confluence pages (CQL); prints the matching pages.
#
# Usage: ./search.sh [-x <exclude-file>] [-s <space-key>] [-a <ancestor-id>] [-n <max>] "<text>"
#   -x  pages in the exclude file and their subpages are left out of the results
#   -s  space to search (default: lmustatistics)
#   -a  only search below this page
#   -n  maximum number of results (default: all)
# Per hit (each page once): title, page ID, URL, and an excerpt with **matches**.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

usage() { echo "usage: search.sh [-x <exclude-file>] [-s <space-key>] [-a <ancestor-id>] [-n <max>] \"<text>\"" >&2; exit 2; }
EXCLUDE_FILE="" SPACE="lmustatistics" ANCESTOR="" MAX=0
while getopts "x:s:a:n:" opt; do
  case "$opt" in
    x) EXCLUDE_FILE="$OPTARG" ;;
    s) SPACE="$OPTARG" ;;
    a) ANCESTOR="$OPTARG" ;;
    n) MAX="$OPTARG" ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ $# -eq 1 && -n "$1" ]] || usage
EXCLUDED="$(conf_excluded_ids "$EXCLUDE_FILE")"

CQL="$(python3 - "$1" "$SPACE" "$ANCESTOR" "$EXCLUDED" <<'PY'
import sys
text, space, ancestor, excluded = sys.argv[1:5]
quote = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
cql = f"type = page and space = {quote(space)} and text ~ {quote(text)}"
if ancestor:
    cql += f" and ancestor = {ancestor}"
if excluded:
    cql += f" and id not in ({excluded}) and ancestor not in ({excluded})"
print(cql)
PY
)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# One request per batch of results; the API's `_links.next` signals more.
LIMIT=100
start=0
while :; do
  batch_file="$TMP_DIR/batch-$(printf '%05d' "$start").json"
  conf_curl --get "$CONF_BASE/rest/api/search" \
    --data-urlencode "cql=$CQL" \
    --data-urlencode "limit=$LIMIT" \
    --data-urlencode "start=$start" \
    --data-urlencode "excerpt=highlight" \
    --data-urlencode "expand=content.ancestors" > "$batch_file"
  start=$((start + LIMIT))
  (( MAX > 0 && start >= MAX )) && break
  python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get("_links", {}).get("next") else 1)' \
    "$batch_file" || break
done

python3 - "$TMP_DIR" "$EXCLUDED" "$MAX" "$CONF_BASE" <<'PY'
import sys, json, re, os, glob
tmp_dir, excluded, max_results, base = sys.argv[1:5]
excluded = set(filter(None, excluded.split(",")))
max_results = int(max_results)
seen, total = set(), "?"
for batch in sorted(glob.glob(os.path.join(tmp_dir, "batch-*.json"))):
    d = json.load(open(batch))
    if d.get("statusCode"):
        sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")
    total = d.get("totalSize", total)
    for r in d["results"]:
        content = r.get("content", {})
        page_id = content.get("id")
        # Second line of defence in case the CQL exclusion ever misses a page.
        chain = {a["id"] for a in content.get("ancestors", [])} | {page_id}
        if page_id in seen or chain & excluded:
            continue
        if max_results and len(seen) >= max_results:
            break
        seen.add(page_id)
        excerpt = re.sub(r"@@@hl@@@(.*?)@@@endhl@@@", r"**\1**", r.get("excerpt", ""))
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        print(f'- {content.get("title")} — `{page_id}`\n'
              f'  {base}{r.get("url", "")}\n'
              f'  > {excerpt}')
print(f"\n{len(seen)} pages shown of {total} total matches.")
PY
