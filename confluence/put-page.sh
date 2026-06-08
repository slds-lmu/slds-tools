#!/usr/bin/env bash
# Push a local storage-format file back to a Confluence page.
# Auto-reads the current version and increments it.
#
# Usage: ./put-page.sh <page-id> <bodyfile> [message]
#
# SAFETY: by default refuses to write to any page other than the sandbox
# "BB Test Page" (ID 2781779130). Override only deliberately by setting
# CONF_ALLOW_ANY_PAGE=1 — institute pages are shared and not ours to edit.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

PAGE_ID="${1:?usage: put-page.sh <page-id> <bodyfile> [message]}"
BODYFILE="${2:?usage: put-page.sh <page-id> <bodyfile> [message]}"
MSG="${3:-Edit via Claude Code}"
SANDBOX_ID="2781779130"

if [[ "$PAGE_ID" != "$SANDBOX_ID" && "${CONF_ALLOW_ANY_PAGE:-0}" != "1" ]]; then
  echo "REFUSING to write to page $PAGE_ID (only sandbox $SANDBOX_ID allowed)." >&2
  echo "Set CONF_ALLOW_ANY_PAGE=1 to override — but institute pages are not ours to edit." >&2
  exit 1
fi

META_FILE="$(mktemp)"
PAYLOAD_FILE="$(mktemp)"
trap 'rm -f "$META_FILE" "$PAYLOAD_FILE"' EXIT

# Current metadata (need title, space key, version).
conf_curl "$CONF_BASE/rest/api/content/$PAGE_ID?expand=version,space" > "$META_FILE"

# Build the PUT payload (version = current + 1).
python3 - "$PAGE_ID" "$BODYFILE" "$MSG" "$META_FILE" "$PAYLOAD_FILE" <<'PY'
import sys, json
page_id, bodyfile, msg, meta_file, out_file = sys.argv[1:6]
meta = json.load(open(meta_file))
if meta.get("statusCode"):
    sys.exit(f"ERROR {meta['statusCode']}: {meta.get('message')}")
body = open(bodyfile).read()
payload = {
    "id": page_id,
    "type": "page",
    "title": meta["title"],
    "space": {"key": meta["space"]["key"]},
    "version": {"number": meta["version"]["number"] + 1, "message": msg},
    "body": {"storage": {"representation": "storage", "value": body}},
}
json.dump(payload, open(out_file, "w"))
sys.stderr.write(f'{meta["title"]}: v{meta["version"]["number"]} -> v{meta["version"]["number"]+1}\n')
PY

RESP_FILE="$(mktemp)"
trap 'rm -f "$META_FILE" "$PAYLOAD_FILE" "$RESP_FILE"' EXIT
conf_curl -X PUT -H "Content-Type: application/json" \
  --data @"$PAYLOAD_FILE" \
  "$CONF_BASE/rest/api/content/$PAGE_ID" > "$RESP_FILE"

python3 - "$RESP_FILE" <<'PY'
import sys, json
d = json.load(open(sys.argv[1]))
if d.get("statusCode"):
    sys.exit(f"ERROR {d['statusCode']}: {d.get('message')}")
print(f'OK: "{d["title"]}" now v{d["version"]["number"]}')
PY
