#!/usr/bin/env bash
# Fetch a Confluence page's storage-format body to a local file.
#
# Usage: ./get-page.sh <page-id> [outfile]
#   Default outfile: page-<page-id>.xhtml
# Prints the page title and current version number to stderr.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

PAGE_ID="${1:?usage: get-page.sh <page-id> [outfile]}"
OUT="${2:-page-${PAGE_ID}.xhtml}"

JSON_FILE="$(mktemp)"
trap 'rm -f "$JSON_FILE"' EXIT

conf_curl "$CONF_BASE/rest/api/content/$PAGE_ID?expand=body.storage,version" > "$JSON_FILE"

python3 - "$OUT" "$JSON_FILE" <<'PY'
import sys, json
out, json_file = sys.argv[1], sys.argv[2]
d = json.load(open(json_file))
if d.get("statusCode"):
    sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")
ver, title = d["version"]["number"], d["title"]
with open(out, "w") as f:
    f.write(d["body"]["storage"]["value"])
sys.stderr.write(f'Saved "{title}" v{ver} -> {out}\n')
PY
