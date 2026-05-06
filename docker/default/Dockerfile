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

# --- R packages (CRAN tooling + mlr3 ecosystem, via pak) ----------------------
# pak resolves and installs binary packages across PPM + r-universe with no
# source fallback, so any "package missing on Linux noble" condition surfaces
# as a hard pak error rather than a slow source-compile attempt that may also
# fail. See install_packages.R for the package list, repository policy, and
# failure handling.
#
# Install script lives in install_packages.R (kept out of the Dockerfile so
# the build works with both BuildKit and the legacy builder — Dockerfile-level
# heredocs are a BuildKit-only feature).
COPY install_packages.R /tmp/install_packages.R
RUN Rscript /tmp/install_packages.R && rm /tmp/install_packages.R

# --- R runtime defaults: PPM as the CRAN mirror -------------------------------
# /etc/R/Rprofile.site runs at every R startup, so install.packages("...")
# inside the running container lands binary noble packages from PPM by
# default. Copied AFTER install_packages.R intentionally — the build-time
# layer must keep using pak's own repo config, not these runtime defaults.
#
# The post-COPY sanity check fails the build if Rprofile.site is not picked
# up by R at startup (wrong path, conffile shadowing, packaging change in a
# future r-base release, ...). Without it, a path regression would silently
# leave PPM unset and downgrade every runtime install.packages() call to
# source builds against the default unset CRAN mirror — which is the kind
# of failure that wouldn't be noticed until someone wonders why their image
# takes 20 min to add a package.
COPY Rprofile.site /etc/R/Rprofile.site
RUN R -q -e 'stopifnot(grepl("packagemanager.posit.co", getOption("repos")[["CRAN"]]))'

# --- Python (3.12 from Ubuntu 24.04) -----------------------------------------
# Ubuntu 24.04 ships /usr/lib/python3.12/EXTERNALLY-MANAGED (PEP 668), which
# blocks plain `pip install` outside a venv with an "externally-managed-
# environment" error. PEP 668 protects host systems where apt and pip both
# manage Python — a problem this image doesn't have, since every Python
# package below is pip-installed (no apt-installed `python3-numpy` etc.).
# Deleting the marker lets `pip install` write system-wide to
# /usr/local/lib/python3.12/dist-packages, which is the simplest mental model
# for a single-purpose container.
RUN apt-get update && apt-get install -y --no-install-recommends \
        # python3: Python 3.12 interpreter (Ubuntu 24.04 default)
        python3 \
        # python3-pip: pip package installer
        python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && rm /usr/lib/python3.12/EXTERNALLY-MANAGED

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
# uv: Rust-based pip/pyenv replacement.
RUN pip install --no-cache-dir uv

# --- Playwright + Chromium ---------------------------------------------------
# playwright: browser-automation library; --with-deps invokes apt to install
# the OS-level libraries Chromium needs to run headless.
RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

# --- Developer tools (gh, vim, zsh, fzf) -------------------------------------
# gh requires its own apt repo; the rest are plain Ubuntu apt packages.
#
# Note on path-include: Ubuntu's docker base image ships
# /etc/dpkg/dpkg.cfg.d/excludes which strips /usr/share/doc/* to keep the
# image slim. fzf's shell integration files (key-bindings.zsh, completion.zsh)
# live there, so without an opt-in they get filtered out and Ctrl-R / Ctrl-T
# / Alt-C don't bind. We add a dpkg path-include for fzf's examples directory
# BEFORE running apt-install.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod a+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && echo 'path-include=/usr/share/doc/fzf/examples/*' \
        > /etc/dpkg/dpkg.cfg.d/zz-keep-fzf-shell-integration \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        # gh: GitHub CLI (`gh pr create`, `gh issue list`, etc.)
        gh \
        # vim: text editor
        vim \
        # zsh: alternative shell, used as the default CMD below
        zsh \
        # zsh-autosuggestions: ghost-text completion of past commands as you type
        zsh-autosuggestions \
        # zsh-syntax-highlighting: colorizes commands on the command line
        zsh-syntax-highlighting \
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

# --- Shell setup -------------------------------------------------------------
# Make root's login shell zsh (so /etc/passwd matches CMD), expose $SHELL so
# subprocesses (tmux, git, sub-shells) know what they're inside, and install
# starship as the prompt. The `plain-text-symbols` preset avoids requiring a
# Nerd Font in the host terminal — works in plain xterm, Konsole, GNOME
# Terminal, macOS Terminal, Windows Terminal, etc.
RUN curl -fsSL https://starship.rs/install.sh \
        | sh -s -- --yes --bin-dir /usr/local/bin \
    && chsh -s /bin/zsh root \
    && mkdir -p /root/.config \
    && starship preset plain-text-symbols -o /root/.config/starship.toml

# Ship a minimal zshrc that wires up completions, history, fzf keybindings,
# the two zsh plugins installed above, and the starship prompt. See the file
# itself for inline comments. Users override this by mounting their own
# .zshrc or by layering a project Dockerfile.
COPY zshrc /root/.zshrc

ENV SHELL=/bin/zsh

# Default shell when running `docker run -it`.
CMD ["/bin/zsh"]
