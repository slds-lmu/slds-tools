#!/usr/bin/env bash
# Push a page's local working copy (from get-page.sh) back to Confluence.
#
# Usage: ./put-page.sh -d <pages-dir> [-n] <page-id> "<edit message>"
#   Pushes <pages-dir>/<id>_<title>.xhtml and prints the diff against the
#   pulled copy. Afterwards re-pulls the page, so the local files and the
#   .meta.json match the new version.
#   -n  dry run: do all checks and show the diff, but don't push
#
# VERSION GUARD: Refuses if the live page's version number or last-edit time
# differs from the .meta.json written at pull time, i.e. someone edited the
# page since — pull again and redo the edit. The PUT also sends
# version = pulled + 1, so Confluence itself rejects an edit that lands
# between our check and the write.
#
# SAFETY: By default refuses to write anywhere except the sandbox
# "BB Test Page" (ID 2781779130) and its subpages. Override only deliberately by
# setting CONF_ALLOW_ANY_PAGE=1 — institute pages are shared and not ours to edit.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/conf-lib.sh"

usage() { echo "usage: put-page.sh -d <pages-dir> [-n] <page-id> \"<edit message>\"" >&2; exit 2; }
PAGES_DIR="" DRY_RUN=0
while getopts "d:n" opt; do
  case "$opt" in
    d) PAGES_DIR="$OPTARG" ;;
    n) DRY_RUN=1 ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ -n "$PAGES_DIR" && $# -eq 2 && -n "$2" ]] || usage
PAGE_ID="$1"
MSG="$2"

shopt -s nullglob
META_FILES=("$PAGES_DIR/${PAGE_ID}"_*.meta.json)
shopt -u nullglob
if [[ ${#META_FILES[@]} -ne 1 ]]; then
  echo "ERROR: expected exactly one ${PAGE_ID}_*.meta.json in $PAGES_DIR (found ${#META_FILES[@]}) — run get-page.sh first." >&2
  exit 1
fi
FILE_BASE="${META_FILES[0]%.meta.json}"

LIVE_FILE="$(mktemp)"
PAYLOAD_FILE="$(mktemp)"
RESP_FILE="$(mktemp)"
trap 'rm -f "$LIVE_FILE" "$PAYLOAD_FILE" "$RESP_FILE"' EXIT

conf_curl "$CONF_BASE/rest/api/content/$PAGE_ID?expand=version,space,ancestors" > "$LIVE_FILE"

# Checks + diff; writes the PUT payload only if there is something to push.
python3 - "$FILE_BASE" "$LIVE_FILE" "$PAYLOAD_FILE" "$MSG" "$CONF_SANDBOX_ID" \
  "${CONF_ALLOW_ANY_PAGE:-0}" "$DRY_RUN" <<'PY'
import sys, json, re, difflib
file_base, live_file, payload_file, msg, sandbox_id, allow_any, dry_run = sys.argv[1:8]
live = json.load(open(live_file))
if live.get("statusCode"):
    sys.exit(f"ERROR {live['statusCode']}: {live.get('message')}")
meta = json.load(open(file_base + ".meta.json"))
work = open(file_base + ".xhtml").read()
pulled = open(file_base + ".pulled.xhtml").read()

chain = [a["id"] for a in live.get("ancestors", [])] + [live["id"]]
if sandbox_id not in chain and allow_any != "1":
    sys.exit(f"REFUSING to write to page {live['id']} (only the sandbox {sandbox_id} and its subpages are allowed).\n"
             "Set CONF_ALLOW_ANY_PAGE=1 to override — but institute pages are not ours to edit.")

lv = live["version"]
if (lv["number"], lv["when"]) != (meta["version"], meta["version_when"]):
    sys.exit(f'REFUSING: "{live["title"]}" changed since pull.\n'
             f'  pulled: v{meta["version"]} ({meta["version_when"]}, pulled {meta["pulled_at"]})\n'
             f'  live:   v{lv["number"]} ({lv["when"]} by {lv.get("by", {}).get("displayName")}: '
             f'"{lv.get("message", "")}")\n'
             "Pull again (get-page.sh; -f discards local edits, so save them first) and redo the edit.")

if work == pulled:
    print("No local changes — nothing to push.")
    sys.exit(0)

# Storage format is often one long line; split between tags so the diff is readable.
def tag_lines(s):
    return re.sub(r">\s*<", ">\n<", s).splitlines(keepends=True)
diff = list(difflib.unified_diff(tag_lines(pulled), tag_lines(work), "pulled", "local", n=2))
sys.stdout.writelines(line if line.endswith("\n") else line + "\n" for line in diff)

if dry_run == "1":
    print(f'Dry run: would push "{live["title"]}" v{meta["version"]} -> v{meta["version"] + 1}.')
    sys.exit(0)

payload = {
    "id": live["id"],
    "type": "page",
    "title": live["title"],
    # No "space": not required for updates, and an accidentally false key could move the page.
    "version": {"number": meta["version"] + 1, "message": msg},
    "body": {"storage": {"representation": "storage", "value": work}},
}
json.dump(payload, open(payload_file, "w"))
sys.stderr.write(f'{live["title"]}: v{meta["version"]} -> v{meta["version"] + 1}\n')
PY

[[ -s "$PAYLOAD_FILE" ]] || exit 0

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

# Re-pull: confirms the change landed and stores the server's (possibly
# normalised) body + new version as the new baseline.
"$CONF_DIR/get-page.sh" -d "$PAGES_DIR" -f "$PAGE_ID"
