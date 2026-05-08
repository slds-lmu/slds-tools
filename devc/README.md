# `devc`

Open Cursor attached to a docker dev container for the current project.

## Prerequisites

- `docker` on PATH.
- `cursor` CLI on PATH (Cursor → Command Palette → "Install 'cursor' command").
- Image `ghcr.io/slds-lmu/default:latest` available locally or pullable.

## Usage

```sh
devc cursor    # ensure container is running, open a Cursor window at /workspace
devc stop      # stop (and remove) this project's container
devc list      # show all devc containers across projects
devc stopall   # stop every running devc container
```

`devc cursor`:

- Resolves the project directory: `git rev-parse --show-toplevel`, or `$PWD`
  if not in a git repo.
- Picks a stable container name based on the project dir, e.g.
  `/home/alice/projects/foo` → `devc-foo-cf1a406a7167`.
- If no container by that name exists, creates one in the background
  (`docker run -d --rm ... sleep infinity`) with the project dir
  bind-mounted at `/workspace` (read-write, as root). If one already
  exists, leaves it alone.
- Opens a Cursor window attached to that container at `/workspace`.

## Lifecycle

Cursor attaches to a running container, so the container must stay up the
whole time you have a window open. Run `devc stop` when you're done.
In-container state (installed packages, shell history) is gone after a stop.

## Claude login does not persist across container recreations

The container is created with `docker run --rm` and the only bind-mount is
the project at `/workspace`. Anything Claude writes to its config dir
(`~/.claude/` inside the container) lives on the container's writable layer
and is destroyed when the container goes away — i.e. on `devc stop` or a
host reboot. The next `devc cursor` creates a fresh container, and Claude
asks you to log in again.

Within a single container's lifetime, opening multiple Cursor windows
reuses the same container, so the login persists across windows.

### Why we don't bind-mount the host's `~/.claude`

The obvious "fix" — `-v ~/.claude:/root/.claude` — would persist the login
indefinitely, but it breaks the sandbox that's the whole point of `devc`:

- **Credential exposure.** Your host `~/.claude` holds OAuth tokens, MCP
  auth (Gmail, Calendar, Drive, ...), and session data. Anything the
  in-container Claude executes — including untrusted code it runs on your
  behalf — can read and exfiltrate those credentials.
- **Write-back contamination.** The container would write sessions,
  history, telemetry, and skill state back into your host config. A buggy
  or compromised container run pollutes (or corrupts) your host Claude.
- **Concurrency.** Two `devc` containers running in parallel for different
  projects would fight over the same `~/.claude` files (sessions,
  `history.jsonl`, caches).

### Options if you want persistence anyway

1. **Live with re-login.** Default behaviour. Strongest isolation.
2. **Named docker volume** for the container's `~/.claude`, e.g.
   `-v devc-claude-<project>:/root/.claude`. Login persists across
   container recreations, the volume is isolated from the host, and each
   project gets its own. This is the recommended trade-off if re-login is
   too painful.
3. **Bind-mount host `~/.claude`.** Maximum convenience, none of the
   sandboxing. Only consider this if you fully trust everything that will
   ever run inside the container.

`devc` currently implements option 1.

