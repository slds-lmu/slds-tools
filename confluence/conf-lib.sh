#!/usr/bin/env bash
# Shared helpers for talking to LMU Confluence.
# Source this from other scripts: `source conf-lib.sh`
set -euo pipefail

CONF_BASE="${CONF_BASE:-https://collab.dvb.bayern}"

# Resolve the PAT from $LMU_CONFLUENCE_PAT or ./.pat (gitignored).
conf_token() {
  local here token src
  src="${BASH_SOURCE[0]:-$0}"   # bash: BASH_SOURCE; fallback: $0
  here="$(cd "$(dirname "$src")" && pwd)"
  token="${LMU_CONFLUENCE_PAT:-}"
  if [[ -z "$token" && -f "$here/.pat" ]]; then
    token="$(tr -d '[:space:]' < "$here/.pat")"
  fi
  if [[ -z "$token" ]]; then
    echo "ERROR: no token (set LMU_CONFLUENCE_PAT or create .pat)" >&2
    return 1
  fi
  printf '%s' "$token"
}

# conf_curl <curl args...> — curl with auth + JSON accept headers preset.
conf_curl() {
  local token; token="$(conf_token)"
  curl -sS \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/json" \
    "$@"
}
