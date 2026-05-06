# `devc`

Open Cursor attached to a docker dev container for the current project.

## Prerequisites

- `docker` on PATH.
- `cursor` CLI on PATH (Cursor → Command Palette → "Install 'cursor' command").
- Image `ghcr.io/slds-lmu/default:latest` available locally or pullable

## Usage

```sh
devc cursor   # ensure container is running, open a Cursor window at /workspace
devc stop     # stop (and remove) this project's container
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

The container must be infinitely open for `cursor`.
So you must run `devc stop` when you are done.
In-container state (installed packages, shell history) is gone after a stop. 

To list devc containers across projects: `docker ps --filter name=devc-`.

