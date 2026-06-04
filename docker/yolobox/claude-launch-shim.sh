#!/bin/bash
# claude-launch-shim.sh — wrapper installed at /usr/local/bin/claude.
#
# Purpose
#   Copy the host's Claude Code plugin directory into the container on first
#   launch, then exec the real `claude` binary. This replaces the former
#   read-write bind mount of the host plugin store.
#
# Why
#   Mounting ~/.claude/plugins read-write into the sandbox is a two-way door:
#   code written from inside the container lands in the host's real plugin
#   store, which the host's Claude Code then executes on its next launch —
#   i.e. persistent code execution on the host. Exposing the plugins
#   READ-ONLY at a staging path and copying them into a container-local,
#   writable tree closes that vector while still giving Claude Code's
#   marketplace loader the writable directory it needs at startup (a
#   read-only mount there causes EROFS and breaks /plugin).
#
# Mechanism
#   The yolobox config bind-mounts the host plugin dir read-only at
#   $STAGE (see sysadmin stow/yolobox/.config/yolobox/config.toml). On the
#   first `claude` launch in this container we copy $STAGE -> $DEST and
#   rewrite the absolute host paths the plugin registry embeds so they point
#   at the container home. A sentinel in /tmp makes this run once per
#   container boot rather than on every `claude` invocation.
#
#   Launch chain: `claude` -> /opt/yolobox/bin/claude (upstream wrapper, adds
#   --dangerously-skip-permissions) -> /usr/local/bin/claude (this shim) ->
#   $REAL. No recursion: $REAL is addressed by absolute path and is not named
#   `claude` on PATH.
#
# Design notes / portability
#   - The host-path prefix is derived from the registry files themselves
#     (matches /home/<user>, /Users/<user>, ... — any user or OS), so nothing
#     is hardcoded to one machine. Works fleet-wide.
#   - Sync is one-way (host -> container); host-side plugin changes propagate
#     in on the next container boot. No persistence back to the host.
set -u

STAGE=/host-claude-plugins                                                   # read-only host plugin mount
DEST="$HOME/.claude/plugins"                                                 # container-writable copy
REAL=/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe    # the real Claude Code binary
SENTINEL=/tmp/.slds-plugins-synced                                           # "already synced this boot" marker

# Sync once per container boot, only if the read-only staging mount is present.
if [ -d "$STAGE" ] && [ ! -e "$SENTINEL" ]; then
  rm -rf "$DEST"
  mkdir -p "$(dirname "$DEST")"
  cp -a "$STAGE" "$DEST"

  # Normalize the absolute host paths embedded by the plugin registry to the
  # container home. Only these two files reference host paths; the prefix is
  # taken from the file, so any host user / OS layout is handled.
  for f in "$DEST/installed_plugins.json" "$DEST/known_marketplaces.json"; do
    [ -f "$f" ] && sed -E -i "s#\"[^\"]*/\.claude/plugins#\"$HOME/.claude/plugins#g" "$f"
  done

  touch "$SENTINEL" 2>/dev/null || true
fi

exec "$REAL" "$@"
