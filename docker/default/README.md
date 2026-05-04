# `default` image

The group's everyday CPU image — Ubuntu 24.04 with R, Python, Latex and common tools.

## Contents

- **OS**: Ubuntu 24.04 LTS, locale `en_US.UTF-8`.
- **R**: latest stable from the CRAN apt repository.
  - Packages (precompiled binaries via Posit Public Package Manager): `tidyverse`, `data.table`, `mlr3`, `ggplot2`, `knitr`.
- **Python**: 3.12 from Ubuntu, in a venv at `/opt/venv` (on `PATH` by default).
  - Packages: `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `jupyter`, `torch` (CPU-only wheel).

## Outputs

Each CI build publishes three tags pointing at the same image:

```
ghcr.io/slds-lmu/default:latest         # moves with every build
ghcr.io/slds-lmu/default:<git-sha>      # immutable per commit
ghcr.io/slds-lmu/default:YYYY-MM-DD     # human-readable snapshot
```

Old images are never auto-deleted — previous `<git-sha>` and date tags remain pullable indefinitely.

## Versioning policy (read this if you base a paper on this image)

`:latest` has floating versions: each rebuild may pick up a newer R, newer CRAN/PyPI packages, or new system libs. Use it for teaching, scripting, and throwaway work.

For anything that has to reproduce later — papers, benchmarks, archived experiments — pin to an immutable reference in your repo's `Dockerfile`:

```Dockerfile
FROM ghcr.io/slds-lmu/default@sha256:<digest>
```

### Finding the digest

The `<digest>` is a content-addressed `sha256:...` string that identifies the exact image bytes. Three ways to look it up:

1. **GitHub UI** — go to https://github.com/orgs/slds-lmu/packages/container/package/default. Each tag lists its `OS / Arch` and a `Digest sha256:...` row you can copy.

2. **`docker pull` output** — pulling a tag prints the digest:

   ```sh
   $ docker pull ghcr.io/slds-lmu/default:latest
   latest: Pulling from slds-lmu/default
   ...
   Digest: sha256:9f3c1a4b8e2d6f7a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a
   Status: Downloaded newer image for ghcr.io/slds-lmu/default:latest
   ```

3. **`docker inspect`** — after pulling, fetch the digest directly:

   ```sh
   $ docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/slds-lmu/default:latest
   ghcr.io/slds-lmu/default@sha256:9f3c1a4b8e2d6f7a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a
   ```

### Example: pinning in a paper repo

```Dockerfile
FROM ghcr.io/slds-lmu/default@sha256:9f3c1a4b8e2d6f7a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a

WORKDIR /paper
COPY . .
CMD ["Rscript", "run_experiments.R"]
```

That pin will resolve to *exactly* the same bytes today, in three years, on any machine — independent of what `:latest` is doing.

Bump the pin deliberately when you need newer packages; don't track `:latest` silently. Breaking changes to this image will be announced via a `:vN` tag bump (`:v1` → `:v2`).

## How to use

Build locally:

```sh
docker build -t slds-default docker/default
```

Run interactively:

```sh
docker run --rm -it slds-default
```

Pull the published image:

```sh
docker pull ghcr.io/slds-lmu/default:latest
```

## Files

- [`Dockerfile`](./Dockerfile) — image definition.
