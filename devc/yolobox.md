# `devc` vs `yolobox`

Notes from comparing this repo's `devc` script against
<https://github.com/finbarr/yolobox>, covering the conceptual diff,
concrete advantages, how to actually run yolobox, its config knobs, the
Cursor question, and what you'd lose by staying on `devc`.

## Shared goal

Both tools wrap AI coding agents (Claude Code, Codex, …) in containers so
a misbehaving agent can't trash the host. The project is mounted, host
secrets stay out of reach, and the agent runs with high autonomy inside
the sandbox.

## What each one is

### `devc` (this repo, ~120 lines of bash)

- One hard-coded image (`ghcr.io/slds-lmu/default:latest`), one mount
  (project → `/workspace`), one mode.
- Container is a long-running `sleep infinity` started lazily by
  `devc cursor`; **Cursor attaches** to it via
  `vscode-remote://attached-container+<hex>/...`. The agent lives inside
  the Cursor remote.
- Subcommands: `cursor | stop | list | stopall`. Container name is
  `devc-<basename>-<sha12(projectdir)>`.
- `docker run --rm` → "running or doesn't exist", no graveyard, reboot =
  clean slate.
- Deliberately **no** host `~/.claude` mount; the README enumerates the
  trade-offs (credential exposure, write-back contamination, concurrency)
  and lands on "re-login each time" as the default, with named-volume as
  the suggested middle ground.

### `yolobox` (finbarr/yolobox, Go CLI)

- Generic agent launcher:
  `yolobox claude | codex | shell | run <cmd> | fork --name ...`.
  Tool-agnostic.
- Docker **and** Podman (and Apple's container runtime), auto-detected.
- Runs as user `yolo` with sudo inside, bridge networking on by default.
- Project-level `.yolobox.toml` for extra packages / Dockerfile fragments;
  named volumes persist installs/configs across sessions.
- `fork` mode copies the project so multiple agents can run in parallel
  with Compose namespacing.
- "YOLO mode" aliases that skip permission prompts; RTK command
  compression; readonly-project mode with `--exclude` / `--copy-as`;
  runtime context manifest at `/run/yolobox/context.json`.

### Side-by-side

| Axis           | `devc`                                    | `yolobox`                                       |
|----------------|-------------------------------------------|-------------------------------------------------|
| Implementation | bash, ~120 LOC                            | Go CLI, multi-package                           |
| Agent surface  | Cursor-attached (agent runs in remote)    | direct CLI per agent (`claude`, `codex`, …)     |
| Runtimes       | Docker only                               | Docker / Podman / Apple                         |
| Image          | one fixed image                           | base image + per-project `.yolobox.toml`        |
| Persistence    | none by default (writable layer dies)     | named volumes for tool state                    |
| Parallelism    | one container per project dir (hash-named)| explicit `fork` for parallel sandboxes          |
| Host creds     | never mounted; re-login each container    | named volumes / user `yolo`, more flexible      |
| Network/caps   | docker defaults, root in container        | bridge net, `yolo` user with sudo               |

`devc` is a tiny, opinionated Cursor-attach helper for one team's lab
image. `yolobox` is a general-purpose, configurable agent sandbox CLI
with multi-runtime support, persistence, fork-parallelism, and
per-project customization.

## Concrete advantages yolobox brings

1. **Parallel agents on the same project.** `yolobox fork --name foo claude`
   copies the project tree into a namespaced sandbox, so you can have
   two or three Claude sessions racing on different branches/approaches
   of the *same* repo without them stepping on each other's working
   copy. `devc` is hash-keyed on the project dir → exactly one container
   per repo; you'd need to clone the repo to a second path to get two
   agents.
2. **Per-project image extension via `.yolobox.toml`.** If a repo needs,
   say, `ffmpeg` plus a specific `uv` toolchain, you commit those in
   `.yolobox.toml` and every checkout gets the same container. With
   `devc` the image is hard-coded to `ghcr.io/slds-lmu/default:latest` —
   for project-specific tools you either bake a new shared image or
   `apt install` inside the container after every recreate (and lose it
   on `devc stop`, since there's no persistence).

## How to run yolobox on a project

### 1. Install

Per the upstream README:

```bash
# Homebrew / Linuxbrew
brew install finbarr/tap/yolobox

# Script-based
curl -fsSL https://raw.githubusercontent.com/finbarr/yolobox/master/install.sh | bash

# Or download a binary from
# https://github.com/finbarr/yolobox/releases
```

This lands binaries outside the project tree, so per the global
mutation rule it needs an explicit "go" and should be tracked in the
sysadmin manifest (`system-package-manager` skill) before installing.

### 2. Use it on a repo

```bash
cd /path/to/your/project

yolobox claude          # launch Claude Code in a sandbox
yolobox shell           # interactive shell in the sandbox
yolobox run pytest      # one-off command
```

The repo is bind-mounted at its **real** host path (e.g.
`/home/you/project`), not rewritten to `/workspace` like `devc` does.
`$HOME` is **not** mounted, so host tokens (`~/.claude`, etc.) stay on
the host.

### 3. Parallel agents on the same repo

```bash
yolobox fork --name try-a claude
yolobox fork --name try-b claude
```

Each fork gets its own copied working tree.

### Slds-tools-specific note

`/home/bischl/cos/slds-tools` is an umbrella repo. `cd` into the actual
subproject (e.g. `devc/`, `publs/`, `docker/`) before `yolobox claude`
so the mount and any `.yolobox.toml` scope to the thing you're working
on, not the whole umbrella.

## `.yolobox.toml` — `packages`, `env`, `mounts`

Lives at the project root. Minimal example:

```toml
[customize]
packages = ["r-base", "texlive-latex-extra", "ffmpeg"]
env      = ["DEBUG=1", "R_LIBS_USER=/tmp/Rlibs"]
mounts   = ["../shared-libs:/libs:ro", "/mnt/data:/data"]
# readonly_project = true
```

- **`packages`** — apt packages baked into the image at **build time**.
  Yolobox extends its base image with `apt install <those>` and caches
  the result, so the next `yolobox claude` starts instantly. Use this
  for anything you want present in every run.
- **`env`** — environment variables injected at **run time** (each
  container start). Strings in `KEY=VALUE` form. Equivalent to
  `docker run -e KEY=VALUE`. Don't hardcode secrets here — reference
  host env vars or use a separate not-committed config.
- **`mounts`** — extra bind mounts at **run time**, on top of the
  implicit project mount. Same `host:container[:mode]` syntax as
  `docker run -v`. Useful for sibling repos or datasets outside the
  project tree. `:ro` makes a mount read-only, recommended for anything
  you don't want the agent to clobber.

## Cursor + yolobox: not supported

Yolobox's docs and README contain **no mention** of Cursor, VS Code,
devcontainers, attach mode, or remote-SSH. It is a CLI launcher: it
starts a container, runs an agent (or shell) inside, and exits when the
agent exits. There is no documented "long-running container you attach
an editor to" mode.

You *can* hack it: start `yolobox shell` (or `yolobox run sleep infinity`)
to keep a container alive, then manually:

```bash
docker ps                                # find the yolobox container name
name="<that-name>"
hex=$(printf '%s' "$name" | od -An -tx1 | tr -d ' \n')
cursor --folder-uri "vscode-remote://attached-container+${hex}/path/to/project"
```

Caveats:

- The container runs as user `yolo`, not root, so Cursor's server
  install path and file permissions may need fiddling.
- The project is mounted at its *real* host path, not `/workspace`, so
  the URI must match.
- Yolobox's lifecycle assumes the container dies when the agent exits;
  this hack uses it in a mode it isn't designed for.
- Nothing upstream guarantees container-naming or mount conventions stay
  stable across versions.

**Recommendation:** treat them as complementary.
`devc cursor` for Cursor-attached editor work (its whole purpose);
`yolobox` for headless agent runs, parallel forks, per-project image
customization. If Cursor-attached is the main workflow, stay on `devc`.

## What you'd really lose by staying on `devc`

Ranked by how much each one bites in practice, with a reimplementation
estimate inside `devc`.

| # | Feature | Real impact | Reimplementation in `devc` |
|---|---|---|---|
| 1 | **`fork` — parallel agents on the same project** | Highest. Two Claude sessions racing different approaches on the same repo is genuinely useful, and `devc` structurally can't do it (one container per project dir, hash-keyed). | **Medium.** Add a `devc fork <name>` subcommand: `rsync -a --exclude .git/objects` the project to `/tmp/devc-forks/<name>`, run a container against that copy, suffix the container name. ~50 lines of bash. Cleanup gets fiddly. |
| 2 | **Per-project `.yolobox.toml` image extension** | Real if projects need diverging toolchains (R + texlive here, ffmpeg there). With `devc` you either bake a fatter shared image or `apt install` after every recreate (lost on stop). | **Medium-hard if done well.** A proper version needs Dockerfile-fragment + content-addressed image cache so rebuilds are fast. ~150 lines + a build cache convention. Or punt: keep one shared image and bake everything the lab needs. |
| 3 | **Named-volume persistence (e.g. `~/.claude` across recreations)** | Real — you re-login after every `devc stop`. README already proposes this as "option 2". | **Trivial.** One line: `-v devc-claude-${name}:/root/.claude` on the `docker run`. ~5 minutes. |
| 4 | **Headless one-off + `shell` modes** (`yolobox run <cmd>`, `yolobox shell`) | Mild — currently you always go through Cursor. Nice when you want a quick sandboxed `pytest` or REPL without opening an editor. | **Trivial.** Two subcommands: `devc shell` → `docker exec -it`, `devc run <cmd>` → `docker exec`. ~10 lines. |
| 5 | **Non-root user (`yolo` + sudo) inside the container** | Real security upgrade — agent processes don't run as root, file ownership on the host bind-mount matches your UID. | **Medium.** Image-side change: add a non-root user, fix `/workspace` ownership, pass `--user $(id -u):$(id -g)`. ~one afternoon on the shared image. |
| 6 | **Multi-runtime (Podman, Apple container)** | None on Linux + Docker. | N/A. |
| 7 | **`--exclude` / `--copy-as` readonly-project mode** | Niche; only matters if you want the agent unable to write the repo. | **Easy** for read-only (`:ro` on the mount). `--copy-as` overlaps with `fork`. |
| 8 | **YOLO-mode CLI aliases, RTK compression, context manifest** | Cosmetic — convenience flags around the agent CLIs. | Trivial to skip; don't bother. |

**Headline:** the only one that's genuinely hard to clone *and* genuinely
useful is `fork`. Everything else is either trivial (3, 4, 7), an
image-side change you'd do once (2, 5), or irrelevant (6, 8).

## Could `devc` be built on top of `yolobox`?

In principle yes, in practice it buys little.

- `yolobox shell` (or `yolobox run sleep infinity`) gives you a
  long-running container.
- A wrapper would read the container name, hex-encode it, and shell out
  to `cursor --folder-uri vscode-remote://attached-container+<hex>/<real-project-path>`.
- That's ~30 lines on top of yolobox, and you inherit `fork`,
  `.yolobox.toml`, named volumes, non-root user.

Caveats that make this less attractive than it sounds:

- Cursor installs its server into the container's home; with user `yolo`
  and persistent named volumes for `~/.yolo` you'd need to make sure the
  install path is right and persists. Trial-and-error.
- Yolobox's lifecycle assumes the container dies when the agent exits;
  Cursor needs it to outlive the agent.
- You'd depend on yolobox's container-naming and mount conventions
  staying stable across versions.

**Pragmatic recommendation.** Keep them separate. Use `devc cursor` for
Cursor-attached editor work; reach for `yolobox` only when you actually
want `fork` (parallel agents). If you want `fork` *and* Cursor attached,
the smaller change is adding a `devc fork` subcommand (item 1 above),
not rebuilding `devc` on top of yolobox.

## Practical workflow: agent in a box, you see what it does, you edit files

The goal "run an agent sandboxed, but still see its actions and edit
files alongside" has three workable shapes.

### Shape A — `devc cursor` (one window does everything)

```bash
cd /path/to/project
devc cursor
```

What you get in one Cursor window:

- **Editor pane** opens `/workspace` inside the container; saves go
  through the bind-mount to the real project on disk.
- **Integrated terminal** is already inside the container. Run `claude`
  there. The agent process is a child of that terminal.
- **Live visibility**: agent edits show up as modified files in Cursor's
  gutter / diff view. Commands and output stream in the terminal.
- **Sandboxing intact**: agent processes can only touch `/workspace`
  and the container FS. No host `~/.claude`, `~/.ssh`, etc.

Most direct match to the stated goal with one window and zero glue.

### Shape B — host Cursor + `yolobox` in its integrated terminal

```
┌─────────── Cursor on host ──────────────────┐
│  editor: /home/bischl/cos/my-project        │  ← edits as bischl, full host FS
│  ┌───── integrated terminal ──────────────┐ │
│  │ $ cd /home/bischl/cos/my-project       │ │
│  │ $ yolobox claude                       │ │  ← host process; spawns container
│  │ (claude streaming output)              │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                  │
                  │ bind mount: real host path → same path in container
                  ▼
       ┌──────── container ──────────┐
       │  user: yolo (sudo inside)   │
       │  claude runs here           │  ← cannot see host outside project
       │  /home/bischl/cos/my-project (same files!) │
       └─────────────────────────────┘
```

What this gets you:

- **Visibility**: agent stdout/stderr in the Cursor terminal.
- **Editing alongside**: Cursor and the agent share the same files via
  the bind-mount; file watchers pick up changes instantly in both
  directions.
- **Sandboxing of the agent**: agent is in the container, cannot reach
  host `~/.ssh`, `~/.claude`, other repos.
- **Parallel forks for free**: a second terminal with
  `yolobox fork --name try-b claude` gets a second agent on a copy.
- **Path identity**: yolobox mounts at the real host path, so any path
  the agent prints is clickable in Cursor.

### Shape C — multiple agents on the same project

Vanilla `devc` cannot do this; either add `devc fork` (~50 LOC, see
above) or use `yolobox fork` while keeping Cursor on host.

## Where does the terminal actually run?

This is the question that determines what's sandboxed and what's not.

| Who runs it                                | Where it executes |
|--------------------------------------------|-------------------|
| You typing in **`devc cursor`** terminal   | **Container**     |
| You typing in **host-Cursor** terminal     | **Host**          |
| `yolobox claude` (the launcher)            | Host              |
| Claude shelling out from inside the agent  | Container         |
| `yolobox shell` / `yolobox run <cmd>`      | Container         |

So with **host-Cursor + yolobox**, only the agent process is sandboxed.
A command *you* type in the Cursor terminal hits your host. If you want
your own commands sandboxed too, you have to enter the box:

```bash
yolobox shell          # interactive shell inside the container
```

## "I don't have the image's software on host"

True for shape B. If the container image has R, texlive, ffmpeg, a
pinned `uv` toolchain etc., your host terminal has none of it; only
the agent inside the container does. To use the image's tools yourself
you either drop into the box or prefix:

```bash
yolobox shell             # interactive
yolobox run pytest -x     # one-shot
yolobox run R --quiet     # one-shot
```

Aliases on host can paper over it (`alias rbox='yolobox run R --quiet'`)
but you end up keeping two shells in your head ("am I on host or in
box?").

With `devc cursor`, the integrated terminal IS the container shell, so
the image's tools are just there. This is the single strongest
ergonomic argument for `devc cursor`.

### `yolobox shell` mostly closes the gap

Open a Cursor terminal → `yolobox shell` → run `R`, `pytest`, `claude`,
whatever. One extra command per terminal tab, alias-able. Residual
differences from `devc cursor`:

1. **One extra command per new terminal.** Trivial friction.
2. **Editor pane on host vs in-container.** Functionally identical for
   editing (same files via bind-mount). Differs only if you want
   Cursor's own process / extensions sandboxed too.
3. **UID mismatch** between you (host) and `yolo` (container) — files
   the agent creates on the bind-mount may be owned by yolo's UID on
   host. With `devc cursor` (root in container) you avoid this.
4. **Lifecycle: worth verifying.** Whether two `yolobox shell`
   invocations from two Cursor terminals attach to the *same*
   container or spawn separate ones determines whether in-container
   state (installed packages, Claude login, running processes) is
   shared between terminals. Quick test:

   ```bash
   # terminal 1
   yolobox shell
   touch /tmp/marker

   # terminal 2
   yolobox shell
   ls /tmp/marker     # exists → same container; missing → separate
   ```

## Decision summary

Stay on **`devc cursor`** as the default for this workflow. It already
gives you sandbox + visibility + editing + the image's tools in one
window, with no UID mismatch and no host/box mode-switching.

Reach for **host-Cursor + `yolobox`** only when you specifically need:

- parallel forks on the same project (`yolobox fork`),
- per-project image extension via `.yolobox.toml`,
- an editor lifecycle independent of the container,
- or an agent CLI other than Claude.

If those needs become routine, the smaller change is usually to add
the missing piece to `devc` (a `fork` subcommand, a named volume for
`~/.claude`, a `shell` / `run` subcommand) rather than switch tools.
