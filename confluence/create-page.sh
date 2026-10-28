#!/usr/bin/env bash
# Create a new Confluence page below an existing one, then pull it (get-page.sh).
#
# Usage: ./create-page.sh -d <pages-dir> <parent-id> "<title>" [bodyfile]
#   bodyfile: storage-format XHTML for the first version (default: empty page),
#   or Markdown (*.md), converted locally with pandoc. The conversion covers
#   plain structure (headings, lists, tables, links, code) — no Confluence
#   macros. Afterwards the page is edited as pulled XHTML like any other.
#   Creating with the body in one request avoids an empty first version.
#   Prints the new page's ID and URL; its local files land in <pages-dir>.
#
# SAFETY: By default the parent must be the sandbox "BB Test Page"
# (ID 2781779130) or one of its subpages. Override only deliberately by
# setting CONF_ALLOW_ANY_PAGE=1 — institute spaces are shared and not ours.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

usage() { echo "usage: create-page.sh -d <pages-dir> <parent-id> \"<title>\" [bodyfile]" >&2; exit 2; }
PAGES_DIR=""
while getopts "d:" opt; do
  case "$opt" in
    d) PAGES_DIR="$OPTARG" ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ -n "$PAGES_DIR" && ( $# -eq 2 || $# -eq 3 ) && -n "$2" ]] || usage
PARENT_ID="$1"
TITLE="$2"
BODYFILE="${3:-}"

PARENT_FILE="$(mktemp)"
PAYLOAD_FILE="$(mktemp)"
RESP_FILE="$(mktemp)"
CONVERTED_FILE="$(mktemp)"
trap 'rm -f "$PARENT_FILE" "$PAYLOAD_FILE" "$RESP_FILE" "$CONVERTED_FILE"' EXIT

if [[ "$BODYFILE" == *.md ]]; then
  pandoc -f gfm -t html --wrap=none "$BODYFILE" -o "$CONVERTED_FILE"
  BODYFILE="$CONVERTED_FILE"
fi

conf_curl "$CONF_BASE/rest/api/content/$PARENT_ID?expand=space,ancestors" > "$PARENT_FILE"

python3 - "$PARENT_FILE" "$PAYLOAD_FILE" "$TITLE" "$BODYFILE" "$CONF_SANDBOX_ID" \
  "${CONF_ALLOW_ANY_PAGE:-0}" <<'PY'
import sys, json
parent_file, payload_file, title, bodyfile, sandbox_id, allow_any = sys.argv[1:7]
parent = json.load(open(parent_file))
if parent.get("statusCode"):
    sys.exit(f"ERROR {parent['statusCode']}: {parent.get('message')}")
chain = [a["id"] for a in parent.get("ancestors", [])] + [parent["id"]]
if sandbox_id not in chain and allow_any != "1":
    sys.exit(f"REFUSING to create a page below {parent['id']} (only below the sandbox {sandbox_id}).\n"
             "Set CONF_ALLOW_ANY_PAGE=1 to override — but institute spaces are not ours to edit.")
body = open(bodyfile).read() if bodyfile else ""
payload = {
    "type": "page",
    "title": title,
    "space": {"key": parent["space"]["key"]},
    "ancestors": [{"id": parent["id"]}],
    "body": {"storage": {"representation": "storage", "value": body}},
}
json.dump(payload, open(payload_file, "w"))
sys.stderr.write(f'Creating "{title}" below "{parent["title"]}" in space {parent["space"]["key"]}\n')
PY

conf_curl -X POST -H "Content-Type: application/json" \
  --data @"$PAYLOAD_FILE" \
  "$CONF_BASE/rest/api/content" > "$RESP_FILE"

NEW_ID="$(python3 - "$RESP_FILE" "$CONF_BASE" <<'PY'
import sys, json
d = json.load(open(sys.argv[1]))
if d.get("statusCode"):
    sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")
sys.stderr.write(f'OK: created "{d["title"]}" (ID {d["id"]}) {sys.argv[2]}{d["_links"]["webui"]}\n')
print(d["id"])
PY
)"

"$CONF_DIR/get-page.sh" -d "$PAGES_DIR" "$NEW_ID"
