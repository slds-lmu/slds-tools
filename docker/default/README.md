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

## Pull and run

```sh
docker pull ghcr.io/slds-lmu/default:latest
docker run --rm -it ghcr.io/slds-lmu/default:latest
```

## Build locally

From the repo root:

```sh
docker build -t slds-default docker/default
docker run --rm -it slds-default
```

First build takes ~30–60 min (texlive-full and the R packages dominate); subsequent builds reuse the layer cache and are much faster. Resulting image is ~8 GB.

## Building a project-specific image on top of `default`

When you start a new project (paper, experiment, course material) and `default` is *almost* what you need, derive your project's image from it instead of rebuilding everything from scratch.

### Skeleton `Dockerfile` for your project repo

```Dockerfile
# Pin to a digest for reproducibility (see "Finding the digest" above).
# A floating tag like :latest works for throwaway / interactive use, but
# breaks reproducibility — the upstream image silently changes under you.
FROM ghcr.io/slds-lmu/default@sha256:9f3c1a4b8e2d6f7a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a

# --- Project-specific extras --------------------------------------------------
# Only install what `default` doesn't already have (check the Contents section).

# Extra R packages from CRAN / Posit Public Package Manager.
RUN R -e "install.packages(c('brms', 'rstan'), \
          repos = 'https://packagemanager.posit.co/cran/__linux__/noble/latest')"

# Extra Python packages into the venv that's already on PATH at /opt/venv.
RUN pip install --no-cache-dir lifelines tslearn

# Extra apt packages (rare — `default` already covers the common cases).
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         libsomething-dev \
#     && rm -rf /var/lib/apt/lists/*

# --- Project code -------------------------------------------------------------
WORKDIR /paper
COPY . .

# What `docker run` does by default.
CMD ["Rscript", "run_experiments.R"]
```

### Build and run

```sh
docker build -t my-paper .

# One-off run — re-runs CMD on the baked-in copy of your code.
docker run --rm my-paper

# Interactive shell with your live code mounted (skips COPY's snapshot).
docker run --rm -it -v "$PWD":/paper my-paper /bin/zsh
```

### Rules of thumb

- **Pin the `FROM` line to an `@sha256:<digest>`, not `:latest`.** Otherwise your project's reproducibility silently drifts whenever this upstream image rebuilds.
- **Don't reinstall things `default` already has.** If you find yourself running `install.packages('tidyverse')` in your project Dockerfile, stop — check the Contents section first.
- **Group extras into as few `RUN` blocks as you can.** Each `RUN` is a layer; many small ones make pulls slow and hurt cache reuse.
- **If three projects in a row need the same extra, propose adding it to `default`** — that's exactly what this image exists for.
- **Optional: publish your project image too.** If you want CI to build and push `ghcr.io/<your-org>/<paper-name>` on every commit, the workflow at [`.github/workflows/docker.yml`](../../.github/workflows/docker.yml) in this repo is a working template you can copy and adapt.

## Files

- [`Dockerfile`](./Dockerfile) — image definition.


