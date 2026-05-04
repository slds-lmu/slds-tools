# `devc` specs

## Invocation

```sh
devc [options...] [command] [mode]  <command-args...>
```

where `[mode]` is one of `quarantine`, `review`, `work`, `install`; and `[command]` is one of `start`, `stop`, `pause`, `restart`, `sync`, `status`, `shell`, `cursor`, `run`, and `env`. `[options...]` are optionally any of `--image|-i [imagename]`, `--projdir|-p [project directory]`, `--cwd|-d [working directory]`, `--one-off|-1`, `--help|-h`.

## Modes

`[mode]` should determine the access rights that the container gets:

- `install`: The `..._cache`-volumes are mounted read-write, and the starting working directory is `/home/dev`. The idea here is that in this mode, one would be able to install required things into the cache volumes, but we don't launch into the `/workspace` as a matter of caution, in case it contains something malicious: the user should need to actively choose to read anything from there.
- `work` should have cache dirs mounted read-only, and with work dir set to `/workspace`.
- `review` everything is mounted read-only, the working dir is mounted to /src and rsync'd to the `$scratch_vol`.
- `quarantine` should be like `review`, except that network is disabled (basically like `quarantine` already does).

The `--name` of the container should be determined by the project name, directory, and mode.

## Commands

`[command]` should indicate what is being done:

- `status` should basically show info about running containers. When command is `status`, then `[mode]` should be optional: if it is given, only show the status for that container, otherwise for all containers for the project dir.
- `start` should ensure that the container is running in the background, basically with `sleep infinity`. If it is already started, `quarantine` / `review` should not re-rsync.
- `stop` should stop and delete the container.
- `shell` should start the container and start interactive shell in the container
- `cursor` should ensure the container is running and open a Cursor window attached to the container. In `install` mode it should open a new window without a folder opened, to avoid automatically reading project files; in other modes it should open the `/workspace` folder. This requires the `cursor` CLI to be available on the host.
- `run` should run a given shell command that is given in `<command args...>`.
- `pause` should stop the container without deleting it
- `restart` should be equivalent to `stop` and then `start`, i.e. stop the container, delete it, then start it again.
- `sync`: synchronize with `rsync` in `quarantine` / `review` mode.
- `env`: manage environment variables that are injected into containers (see below). This command does not start containers and does not take a `[mode]` argument.

for `shell` and `run` only, there is the option `--one-off`: it should basically do podman run `--rm` instead of `-d` (and use a different name so that it does not conflict with running containers).

## Options

The other options:

- `--cwd` should be evaluated first: if it is given, we switch the current working directory to there
- `--projdir` should then be evaluated: if it is not given, use the git rev-parse mechanism that we already have and fall back to the (possibly changed by `--cwd`) PWD. If projdir is given as a relative path, it is evaluated relative to before the PWD was changed by `--cwd`. The final PWD must *always* the project dir, or a subdirectory, i.e. reachable from the project directory without leaving the project directory.
- `--image` works as currently already and takes precedence over project config: if it is not given, `devc` first looks for an image in the project `.devc` file (see below), otherwise the heuristic is used to choose between images.
- `--help` should give some informative help message. If `--help` is given, everything else should be ignored, and it should be possible to do `--help` without any other arguments.
- if no args are given, or if the given arguments are wrong or contradictory, a short message should be printed, indicating how the command should be executed.

## Caches and configuration

- Standard language caches should be persisted via named volumes (e.g. pip, npm, R/renv, R packages).
- Common configuration directories should be provided via volumes (e.g. `~/.config`, Cursor server settings, Claude code settings).
- In `install` mode, these volumes are mounted read-write and configuration paths should be linked so changes persist to the volumes.
- In other modes, these volumes are mounted read-only. Configuration files are rsynced into the home directory on container creation/entry so that config-changes can still be written (but will be container-local).

## Environment variables

- `DEVC_MEM_LIMIT` overrides the default memory limit (default: `16g`).
- `DEVC_PIDS_LIMIT` overrides the default pids limit (default: `2048`).

### Managed container environment

`devc` can persist per-project environment variables on the host and inject them into containers at startup. This is useful for tokens like `GH_TOKEN`.

- Storage location: `${XDG_STATE_HOME:-$HOME/.local/state}/devc/env/`.
- File naming: `env-$(basename "$PROJ_DIR")-$(hash_short "$PROJ_DIR")-<trustlevel>`.
- Trust levels:
  - `trusted` → used for `install` and `work` containers.
  - `untrusted` → used for `review` and `quarantine` containers.
  - `all` → convenience target that applies to both (future-proof for more levels).
- File contents: simple `KEY=VALUE` lines; permissions are set restrictive (0600). Lines are replaced on `add` when the same `KEY` exists.
- Applying changes: updates are picked up by newly started or one-off containers. Restart existing containers to apply changes.

Usage:

```sh
# Add/replace a variable
devc env add trusted GH_TOKEN=ghp_XXXX
devc env add untrusted FOO=bar
devc env add all MY_FLAG=1

# Remove a variable
devc env del trusted GH_TOKEN
devc env del all MY_FLAG

# List variables
devc env list            # both trust levels
devc env list trusted    # just trusted
```

## Image selection

- Project config: if `$PROJ_DIR/.devc` exists, it is parsed as simple `key=value` pairs. The only accepted key for now is `image`. When present, `image=...` sets the image for the project and overrides auto-detection (but is still overridden by `--image`). Example:

  ```ini
  # .devc
  image=devc/r-base:latest
  ```

- Precedence (highest → lowest):
  - `--image` CLI option
  - `.devc` file `image=...`
  - auto-detected language-specific defaults
  - global default `devc/base:latest`

- If `pyproject.toml` or `requirements.txt` exists, the default image should be `devc/python-base:latest` ("python").
- If `renv.lock` or `DESCRIPTION` exists, the default image should be `devc/r-base:latest` ("R").
- If `package.json` or `Cargo.toml` exists, the default image should be `devc/rust-base:latest` ("rust").
- Otherwise, the default image should be `devc/base:latest` (overridable with `--image`).

## Possible Extensions

- `--verbose|-v` argument that logs important info (e.g. which image is used, which paths are used etc). Maybe with extra levels (multiple `-v`) where more info is logged, or where `podman` is also invoked in verbose mode
- `--sudo` mode for `run` / `shell` for installing system dependencies.
