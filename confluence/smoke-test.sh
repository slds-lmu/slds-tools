#!/usr/bin/env bash
# Read-only smoke test against LMU Confluence.
# Reads the PAT via conf-lib.sh (./.pat or $LMU_CONFLUENCE_PAT).
# Fetches the test page's metadata + storage body and prints HTTP status.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

PAGE_ID="663984308"

echo "GET $CONF_BASE/rest/api/content/$PAGE_ID"
conf_curl -w '\nHTTP %{http_code}\n' \
  "$CONF_BASE/rest/api/content/$PAGE_ID?expand=body.storage,version,space"
