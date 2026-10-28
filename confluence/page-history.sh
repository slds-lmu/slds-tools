#!/usr/bin/env bash
# List all versions of a Confluence page, newest first.
#
# Usage: ./page-history.sh [-x <exclude-file>] <page-id>
#   One line per version: number, date + time, author, edit message.
#   -x  pages in the exclude file and their subpages are refused
#   Only version info is fetched, no page contents. To get an old version's
#   body: GET /rest/api/content/<id>?status=historical&version=<n>&expand=body.storage
#
# Uses /rest/experimental/content/<id>/version: not in the documented 9.2 API,
# but present on BayernCollab (Confluence 9.2.26). The documented alternative
# is one request per version via ?status=historical&version=<n>.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

usage() { echo "usage: page-history.sh [-x <exclude-file>] <page-id>" >&2; exit 2; }
EXCLUDE_FILE=""
while getopts "x:" opt; do
  case "$opt" in
    x) EXCLUDE_FILE="$OPTARG" ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ $# -eq 1 ]] || usage
PAGE_ID="$1"
EXCLUDED="$(conf_excluded_ids "$EXCLUDE_FILE")"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

conf_curl "$CONF_BASE/rest/api/content/$PAGE_ID?expand=ancestors" > "$TMP_DIR/page.json"

# Check the exclusion before fetching any version info.
python3 - "$TMP_DIR/page.json" "$EXCLUDED" <<'PY'
import sys, json
page, excluded = json.load(open(sys.argv[1])), sys.argv[2]
if page.get("statusCode"):
    sys.exit(f"ERROR {page['statusCode']}: {page.get('message')}")
chain = {a["id"] for a in page.get("ancestors", [])} | {page["id"]}
if chain & set(filter(None, excluded.split(","))):
    sys.exit(f"REFUSING: page {page['id']} is excluded (or below an excluded page).")
PY

# One request per batch of versions; the API's `_links.next` signals more.
LIMIT=200
start=0
while :; do
  batch_file="$TMP_DIR/batch-$(printf '%05d' "$start").json"
  conf_curl "$CONF_BASE/rest/experimental/content/$PAGE_ID/version?limit=$LIMIT&start=$start" > "$batch_file"
  python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])).get("_links", {}).get("next") else 1)' \
    "$batch_file" || break
  start=$((start + LIMIT))
done

python3 - "$TMP_DIR" <<'PY'
import sys, json, os, glob
tmp_dir = sys.argv[1]
page = json.load(open(os.path.join(tmp_dir, "page.json")))
print(f'# Version history of "{page["title"]}" (`{page["id"]}`)\n')
for batch in sorted(glob.glob(os.path.join(tmp_dir, "batch-*.json"))):
    d = json.load(open(batch))
    # Unknown paths answer with "status-code" instead of the usual "statusCode".
    status = d.get("statusCode") or d.get("status-code")
    if status:
        sys.exit(f"ERROR {status}: {d.get('message')}")
    for v in d["results"]:
        when = v["when"][:16].replace("T", " ")
        by = (v.get("by") or {}).get("displayName", "?")
        minor = " (minor)" if v.get("minorEdit") else ""
        message = f' — "{v["message"]}"' if v.get("message") else ""
        print(f'- v{v["number"]} · {when} · {by}{minor}{message}')
PY
