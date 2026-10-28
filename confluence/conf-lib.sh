#!/usr/bin/env bash
# Shared helpers for talking to LMU Confluence.
# Source this from other scripts: `source conf-lib.sh`
set -euo pipefail

CONF_BASE="${CONF_BASE:-https://collab.dvb.bayern}"
CONF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# "BB Test Page": the only subtree we currently may write to (see README, critical rule).
CONF_SANDBOX_ID="2781779130"

# Resolve the PAT from $LMU_CONFLUENCE_PAT or ./.pat (gitignored).
conf_token() {
  local token
  token="${LMU_CONFLUENCE_PAT:-}"
  if [[ -z "$token" && -f "$CONF_DIR/.pat" ]]; then
    token="$(tr -d '[:space:]' < "$CONF_DIR/.pat")"
  fi
  if [[ -z "$token" ]]; then
    echo "ERROR: no token (set LMU_CONFLUENCE_PAT or create .pat)" >&2
    return 1
  fi
  printf '%s' "$token"
}

# conf_curl <curl args...> — curl with auth + JSON accept headers preset.
# Note: The private token should never show up in the process list -> passed
# as a curl config on stdin. Consequence: Calls to conf_curl can't
# use stdin (e.g. `--data @-`) -> pass request bodies as files.
conf_curl() {
  local token; token="$(conf_token)"
  curl -sS -K - -H "Accept: application/json" "$@" \
    <<< "header = \"Authorization: Bearer $token\""
}

# conf_excluded_ids [exclude-file] — page IDs from the file, comma-separated.
# File format: one page ID per line, `#` starts a comment. An excluded page and
# its whole subtree are never downloaded, listed, or searched (see README).
conf_excluded_ids() {
  local file="${1:-}"
  [[ -n "$file" ]] || return 0
  if [[ ! -f "$file" ]]; then
    echo "ERROR: exclude file not found: $file" >&2
    return 1
  fi
  sed -e 's/#.*//' -e 's/[[:space:]]//g' "$file" \
    | { grep -E '^[0-9]+$' || true; } | paste -sd, -
}
