#!/usr/bin/env bash
# Read-only smoke test against LMU Confluence.
# Reads the PAT from ./.pat (gitignored) or $LMU_CONFLUENCE_PAT.
# Fetches the test page's metadata + storage body and prints HTTP status.
set -euo pipefail

BASE="https://collab.dvb.bayern"
PAGE_ID="663984308"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN="${LMU_CONFLUENCE_PAT:-}"
if [[ -z "$TOKEN" && -f "$here/.pat" ]]; then
  TOKEN="$(tr -d '[:space:]' < "$here/.pat")"
fi
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: no token. Put it in $here/.pat or export LMU_CONFLUENCE_PAT." >&2
  exit 1
fi

echo "GET $BASE/rest/api/content/$PAGE_ID"
curl -sS -w '\nHTTP %{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  "$BASE/rest/api/content/$PAGE_ID?expand=body.storage,version,space"
