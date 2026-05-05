# Purpose: Default SLDS container image — Ubuntu 24.04 base providing R,
#          Python, LaTeX, and a broad set of shell tools, intended as the
#          group's everyday CPU image. Every package below carries a one-line
#          note on what it is and why it is included.

FROM ubuntu:24.04

# Make every shell-form RUN fail-fast. Without this, the default shell is
# `/bin/sh -c` (dash), where chained commands separated by `;` continue past
# errors and broken pipelines (e.g. `curl ... | bash`) hide upstream failures.
# Bash strict mode catches all three:
#   -e            : abort on first non-zero exit
#   -o pipefail   : a pipeline fails if any stage fails (so `curl | bash`
#                   exits non-zero when curl fails, not silently when bash
#                   gets an empty stdin)
#   -c            : execute the following string (Docker passes the RUN body)
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# DEBIAN_FRONTEND=noninteractive: prevent apt prompts (e.g. tzdata) during build.
# LANG/LC_ALL: default to UTF-8 so Unicode I/O in R/Python "just works".
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# --- Base utilities + locale --------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # ca-certificates: trusted root CA bundle for HTTPS to apt/CRAN/PyPI
        ca-certificates \
        # curl: HTTP client used to fetch installer scripts and apt keys
        curl \
        # gnupg: GPG tooling needed to verify third-party apt repository keys
        gnupg \
        # locales: locale data so we can generate en_US.UTF-8 below
        locales \
        # wget: HTTP client used by the CRAN apt-key bootstrap step
        wget \
        # build-essential: gcc/g++/make — required to compile R/Python source packages
        build-essential \
        # pkg-config: helper that lets configure scripts find library headers/flags
        pkg-config \
        # libcurl4-openssl-dev: libcurl headers — required by R curl/httr/httr2
        libcurl4-openssl-dev \
        # libssl-dev: OpenSSL headers — required by R openssl, httr, and many pip wheels
        libssl-dev \
        # libxml2-dev: libxml2 headers — required by R xml2
        libxml2-dev \
        # libfontconfig1-dev: fontconfig headers — required by R systemfonts/ragg
        libfontconfig1-dev \
        # libharfbuzz-dev: harfbuzz headers — required by R textshaping/ragg
        libharfbuzz-dev \
        # libfribidi-dev: fribidi headers — required by R textshaping/ragg
        libfribidi-dev \
        # libfreetype6-dev: freetype headers — required by R ragg/Cairo
        libfreetype6-dev \
        # libpng-dev: libpng headers — PNG output in Cairo/ragg
        libpng-dev \
        # libtiff5-dev: libtiff headers — TIFF output in tiff/ragg
        libtiff5-dev \
        # libjpeg-dev: libjpeg headers — JPEG output in jpeg/ragg
        libjpeg-dev \
        # libgit2-dev: libgit2 headers — required by R gert (native git from R)
        libgit2-dev \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# --- Shell / CLI utilities ----------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # git: VCS used everywhere, including by pak for GitHub-source installs
        git \
        # openssh-client: ssh/scp for git-over-SSH and remote work
        openssh-client \
        # ripgrep: fast recursive grep replacement for code search
        ripgrep \
        # jq: JSON processor for shell pipelines
        jq \
        # unzip: unpack .zip archives
        unzip \
        # zip: create .zip archives
        zip \
        # rsync: efficient file synchronization, local and over ssh
        rsync \
        # less: pager for long files and man-page output
        less \
        # nano: minimal terminal editor for users who don't use vim
        nano \
        # procps: ps/top/free/uptime — basic process inspection
        procps \
        # sudo: privilege escalation when running as a non-root user
        sudo \
        # man-db: man-page index/database so `man <cmd>` returns docs
        man-db \
        # aggregate: CIDR-block aggregation utility (occasional networking task)
        aggregate \
        # tmux: terminal multiplexer for persistent multi-pane sessions
        tmux \
        # htop: interactive process viewer (improved top)
        htop \
        # parallel: GNU parallel — run shell jobs concurrently from a list
        parallel \
    && rm -rf /var/lib/apt/lists/*

# --- Scientific / numerical system libraries ----------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # cmake: build system needed by R/Python packages with CMake configures
        cmake \
        # zlib1g-dev: zlib headers — used by countless compression-aware packages
        zlib1g-dev \
        # libeigen3-dev: Eigen C++ template headers — used by RcppEigen and consumers
        libeigen3-dev \
        # libx11-dev: X11 headers — required by R tcltk and some plotting backends
        libx11-dev \
        # libglpk-dev: GLPK headers — required by R igraph for max-flow / LP
        libglpk-dev \
        # libudunits2-dev: UDUNITS-2 headers — required by R units / sf
        libudunits2-dev \
        # libhiredis-dev: hiredis headers — required by R redux (Redis client)
        libhiredis-dev \
        # libproj-dev: PROJ library headers — required by R sf/terra for reprojection
        libproj-dev \
        # libprotobuf-dev: protobuf headers — required by R RProtoBuf
        libprotobuf-dev \
        # libgdal-dev: GDAL headers — required by R sf/terra/raster for spatial I/O
        libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Document toolchain (pandoc + LaTeX + biber) ------------------------------
# texlive-full pulls the entire Ubuntu-packaged TeX Live distribution (~5 GB)
# so build/render of any reasonable LaTeX/Rnw/Rmd document just works without
# whack-a-mole over missing CTAN packages. Latexmk and biber come along for
# the ride; pandoc/qpdf/tidy/lmodern complete the document toolchain.
#
# Apt resilience is dropped in *here* (not earlier) because this is the first
# layer where a flaky archive.ubuntu.com mirror has a near-certain chance of
# hitting at least one timeout — texlive-full pulls ~3000 individual .deb
# files. Without retries, a single transient connection-refused on any one of
# them aborts the whole `apt-get install`. The 80-retries snippet is written
# to /etc/apt/apt.conf.d/ so it persists in the image and every subsequent
# apt-using layer (CRAN R repo, Python, gh, Node) inherits the same defence.
#   Acquire::Retries        : up to 5 retry attempts per failed .deb fetch
#   Acquire::http::Timeout  : 120s per HTTP connect/read (default 100s);
#                             keeps slow but-not-dead mirrors from being
#                             classified as failures.
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries \
    && echo 'Acquire::http::Timeout "120";' >> /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # pandoc: universal document converter used by knitr/rmarkdown
        pandoc \
        # tidy: HTML/XML tidier for generated documents
        tidy \
        # qpdf: PDF transformation/compression utility used by latexmk
        qpdf \
        # lmodern: Latin Modern fonts — default for many LaTeX documents
        lmodern \
        # texlive-full: complete TeX Live distribution — every CTAN package,
        # every language, every font, plus latexmk, biber, xetex, etc.
        texlive-full \
    && rm -rf /var/lib/apt/lists/*

# --- Latest R from the CRAN apt repository ------------------------------------
# The CRAN-maintained apt repo gives current R instead of Ubuntu's stock 4.3.
RUN wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc \
        | tee /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc > /dev/null \
    && echo "deb https://cloud.r-project.org/bin/linux/ubuntu noble-cran40/" \
        > /etc/apt/sources.list.d/cran.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # r-base: the R interpreter and base packages (the `R` command itself)
        r-base \
        # r-base-dev: R headers/scripts needed to compile R packages from source
        r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# --- R-package source-compile system deps -----------------------------------
# PPM's `__linux__/noble/latest` URL serves pre-compiled binaries for most
# CRAN packages, but FALLS BACK to source tarballs when PPM does not yet
# have a binary for a specific package@version (typically true for the first
# few hours/days after a CRAN release). When that happens, R compiles from
# source in the next layer — and source compiles need the relevant -dev
# system libraries.
#
# The libs below cover the source-compile system requirements for packages
# in the SLDS R stack (tidyverse + mlr3) that aren't already covered by the
# scientific-libs layer above:
#   libuv1-dev      : required by `fs` (it falls back to source whenever
#                     PPM lags CRAN; observed failure on fs 2.1.0 build).
#   libsodium-dev   : required by `sodium` (transitive dep of httr2/oauth flows).
#   libsecret-1-dev : required by `keyring` (used by gh / git auth helpers).
#
# Adding more libs here is the right answer to "package X failed to source-
# compile because lib Y was missing" — keep it scoped to actual R deps so the
# image doesn't bloat with every unrelated -dev package.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libuv1-dev \
        libsodium-dev \
        libsecret-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Core CRAN R packages installed as precompiled binaries via Posit Public
# Package Manager (PPM). PPM serves binary tarballs at the
# `__linux__/noble/latest` URL; install.packages downloads them and R
# CMD INSTALL drops them in without compilation, much faster than the
# source-compile path. When PPM hasn't yet built a binary for a specific
# package version, it falls back to source — see the R-package source-compile
# system deps layer immediately above.
#
# Failure handling: install.packages() emits a *warning* (not an error)
# when a package fails to install — the R process exits 0 either way.
# We verify after the fact by diffing the requested set against
# rownames(installed.packages()) and stop() with a non-zero exit on any
# missing package, so the docker build aborts at this layer instead of
# silently producing an image without the requested R stack.
RUN Rscript - <<'EOF'
options(
    repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/noble/latest"),
    Ncpus = max(1L, parallel::detectCores() - 1L)  # parallel compile if any source pkg slips through
)
pkgs <- c(
    "tidyverse",   # tidyverse: meta-pkg of dplyr/ggplot2/tidyr/readr — standard toolkit
    "data.table",  # data.table: fast in-memory tabular data manipulation
    "ggplot2",     # ggplot2: grammar-of-graphics plotting (also bundled in tidyverse)
    "knitr",       # knitr: dynamic report generation (Rnw / Rmd weaving)
    "devtools"     # devtools: package-development helpers (install_github, document, check)
)
install.packages(pkgs)
missing <- setdiff(pkgs, rownames(installed.packages()))
if (length(missing)) {
    stop("install.packages() failed for: ", paste(missing, collapse = ", "), call. = FALSE)
}
EOF

# --- mlr3 ecosystem (via pak) -------------------------------------------------
# pak resolves and installs binary packages across PPM + r-universe.
#
# Repository policy:
#   - PPM (Posit Public Package Manager): primary CRAN mirror, serves
#     pre-compiled binaries for noble at the `__linux__/noble/latest` URL.
#   - mlr-org.r-universe.dev: r-universe binaries for the latest mlr3
#     development releases (often ahead of CRAN).
#   - community.r-multiverse.org: r-universe binaries for community packages
#     not yet (or never) on CRAN.
# We deliberately do NOT add a source-only fallback like cloud.r-project.org —
# all three repos serve binaries, so pak resolves only binary candidates and
# any "package missing on Linux noble" condition surfaces as a hard pak
# error rather than a slow source-compile attempt that may also fail.
#
# Failure handling: pak::pak() raises a hard error (non-zero R exit) on
# resolution / install failure, but we still post-check installed.packages()
# defensively so a future pak release that downgrades errors to warnings
# still trips this layer.
RUN Rscript - <<'EOF'
Sys.setenv(NOT_CRAN = "true")
install.packages("pak", repos = sprintf("https://r-lib.github.io/p/pak/stable/%s/%s/%s", .Platform$pkgType, R.Version()$os, R.Version()$arch))
pak::repo_add(
    PPM          = "https://packagemanager.posit.co/cran/__linux__/noble/latest",
    mlr3universe = "https://mlr-org.r-universe.dev",
    multiverse   = "https://community.r-multiverse.org")
pkgs <- c(
    "mlr3verse",    # mlr3verse: meta-pkg pulling mlr3 + pipelines + tuning + viz
    "bbotk",        # bbotk: black-box optimization toolkit, optimizer foundation under mlr3tuning
    "mlr3oml",      # mlr3oml: OpenML integration (fetch tasks/datasets from openml.org)
    "mlr3learners"  # mlr3learners: extra learners (xgboost, ranger, glmnet, lightgbm, ...)
)
pak::pak(pkgs, dependencies = TRUE, ask = FALSE)
missing <- setdiff(pkgs, rownames(installed.packages()))
if (length(missing)) {
    stop("pak::pak() failed for: ", paste(missing, collapse = ", "), call. = FALSE)
}
EOF

# --- Python (3.12 from Ubuntu 24.04) -----------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # python3: Python 3.12 interpreter (Ubuntu 24.04 default)
        python3 \
        # python3-pip: pip package installer
        python3-pip \
        # python3-venv: venv module for creating isolated environments
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create a global venv at /opt/venv and put it on PATH so subsequent pip /
# python invocations use it (sidesteps PEP 668's externally-managed lock).
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH
RUN python3 -m venv "$VIRTUAL_ENV"

RUN pip install --no-cache-dir \
        # numpy: n-dim arrays, foundation of the SciPy stack
        numpy \
        # pandas: tabular data analysis
        pandas \
        # scikit-learn: classical ML algorithms
        scikit-learn \
        # matplotlib: standard 2D plotting library
        matplotlib \
        # jupyter: notebooks + jupyter-lab + ipykernel
        jupyter

# --- uv: Astral's fast Python package / project manager ----------------------
# uv: Rust-based pip/pyenv replacement; installed into the venv so it is on PATH.
RUN pip install --no-cache-dir uv

# --- Playwright + Chromium ---------------------------------------------------
# playwright: browser-automation library; --with-deps invokes apt to install
# the OS-level libraries Chromium needs to run headless.
RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

# --- Developer tools (gh, vim, zsh, fzf) -------------------------------------
# gh requires its own apt repo; the rest are plain Ubuntu apt packages.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod a+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # gh: GitHub CLI (`gh pr create`, `gh issue list`, etc.)
        gh \
        # vim: text editor
        vim \
        # zsh: alternative shell, used as the default CMD below
        zsh \
        # fzf: fuzzy finder, integrates with shells for fast file/history search
        fzf \
    && rm -rf /var/lib/apt/lists/*

# --- Node.js (LTS) + global CLIs ---------------------------------------------
# NodeSource provides current LTS for Ubuntu noble; npm globals land in
# /usr/lib/node_modules and are linked into /usr/bin.
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g \
        # claude-code: Anthropic's CLI coding assistant
        @anthropic-ai/claude-code \
        # codex: OpenAI's CLI coding assistant
        @openai/codex

# --- air: Posit's R formatter (Rust binary) ----------------------------------
# air: opinionated R code formatter from Posit (Rust, very fast).
# Installed via the cargo-dist shell installer.
#
# Why we move the binary post-install: the installer is cargo-dist's, NOT
# the cargo CLI's, so it does NOT honour CARGO_HOME. It always drops the
# binary at $HOME/.local/bin/<bin> (`/root/.local/bin/air` during the build)
# and that path is NOT on the runtime PATH for any user. cargo-dist exposes
# CARGO_DIST_FORCE_INSTALL_DIR but that name is liable to change between
# cargo-dist releases; the post-install `mv` is robust against that and
# leaves no behind-image cruft.
#
# Steps below, in order:
#   1. Run the installer (drops `air` at /root/.local/bin/air, also writes
#      `. "$HOME/.local/bin/env"` into .zshrc/.bashrc/.profile so that
#      ~/.local/bin lands on PATH).
#   2. Move the binary to /usr/local/bin so every user finds it on PATH.
#   3. Delete /root/.local and /root/.config/air — the binary lives elsewhere
#      now and nothing else in the image needs that tree.
#   4. Strip cargo-dist's rc-file edits: with /root/.local gone, the source
#      line points at a missing file and emits a "no such file" warning on
#      every shell start. `|| true` keeps the RUN green even if a given rc
#      file doesn't exist on this base image.
RUN curl -LsSf https://github.com/posit-dev/air/releases/latest/download/air-installer.sh | sh \
    && mv /root/.local/bin/air /usr/local/bin/air \
    && rm -rf /root/.local /root/.config/air \
    && sed -i '/\.local\/bin\/env/d' /root/.zshrc /root/.bashrc /root/.profile 2>/dev/null || true

# Default shell when running `docker run -it`.
CMD ["/bin/zsh"]
