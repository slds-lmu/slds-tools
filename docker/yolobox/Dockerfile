FROM ghcr.io/finbarr/yolobox:latest

# Upstream image runs as the unprivileged `yolo` user; switch to root for the
# apt / pip / R installs below. Restore the default user at the end.
USER root

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Locale data (en_US.UTF-8 generated below; LANG/LC_ALL stay C.UTF-8)
    locales \
    # Extra shell utilities
    procps \
    man-db \
    aggregate \
    tmux \
    parallel \
    bc \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    libgit2-dev \
    zlib1g-dev \
    libeigen3-dev \
    libx11-dev \
    libglpk-dev \
    libudunits2-dev \
    libhiredis-dev \
    libproj-dev \
    libprotobuf-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# LaTeX / document toolchain. texlive-full pulls ~3000 .deb
# files, so add apt retry/timeout config first to survive flaky mirrors.
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries \
    && echo 'Acquire::http::Timeout "120";' >> /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        pandoc \
        tidy \
        qpdf \
        lmodern \
        texlive-full \
    && rm -rf /var/lib/apt/lists/*

# CRAN apt repo + R (from slds-tools). Provides current R instead of Ubuntu's stock.
RUN wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc \
        | tee /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc > /dev/null \
    && echo "deb https://cloud.r-project.org/bin/linux/ubuntu noble-cran40/" \
        > /etc/apt/sources.list.d/cran.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        r-base \
        r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# R packages via pak (tidyverse + mlr3 ecosystem). See install_packages.R for
# the package list, PPM date pin, and repository policy.
COPY install_packages.R /tmp/install_packages.R
RUN Rscript /tmp/install_packages.R && rm /tmp/install_packages.R

# Python ML stack. Ubuntu 24.04 ships a PEP 668 marker that
# blocks system-wide `pip install` outside a venv; we remove it because this
# is a single-purpose container that doesn't need PEP 668's host protection.
RUN rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED \
    && pip install --no-cache-dir \
        numpy \
        pandas \
        scikit-learn \
        matplotlib \
        jupyter

# air: Posit's R formatter (Rust binary). The cargo-dist installer drops the
# binary at /root/.local/bin/air; move it to /usr/local/bin so every user
# finds it on PATH, then strip the rc-file edits the installer leaves behind.
RUN curl -LsSf https://github.com/posit-dev/air/releases/latest/download/air-installer.sh | sh \
    && mv /root/.local/bin/air /usr/local/bin/air \
    && rm -rf /root/.local /root/.config/air \
    && sed -i '/\.local\/bin\/env/d' /root/.zshrc /root/.bashrc /root/.profile 2>/dev/null || true

# Interactive shell setup: zsh + plugins + starship prompt. 
# The upstream yolobox base ships fzf but its
# shell-integration scripts under /usr/share/doc/fzf/examples/ are stripped by
# Ubuntu's dpkg.cfg.d/excludes (path-exclude=/usr/share/doc/*). We add a
# path-include for that directory BEFORE reinstalling fzf so the key-bindings
# and completion files get unpacked. Then install zsh and the two plugins.
RUN echo 'path-include=/usr/share/doc/fzf/examples/*' \
        > /etc/dpkg/dpkg.cfg.d/zz-keep-fzf-shell-integration \
    && apt-get update \
    && apt-get install -y --no-install-recommends --reinstall fzf \
    && apt-get install -y --no-install-recommends \
        zsh \
        zsh-autosuggestions \
        zsh-syntax-highlighting \
    && rm -rf /var/lib/apt/lists/*

# starship: cross-shell prompt (Rust binary). The plain-text-symbols preset
# avoids requiring a Nerd Font in the host terminal.
RUN curl -fsSL https://starship.rs/install.sh \
        | sh -s -- --yes --bin-dir /usr/local/bin

# Ship dotfiles for the unprivileged `yolo` user. 
#   .zshrc        — interactive shell behavior, plugin wiring, prompt init
#   .zsh_aliases  — sourced by .zshrc; ls/grep colors, R alias, gccm helpers
# The starship config is composed at build time: the plain-text-symbols preset
# (so no Nerd Font is required) is concatenated with starship-extra.toml (the
# user's format / directory / cmd_duration overrides). All files are owned by
# yolo:yolo so the user can edit them at runtime.
COPY --chown=yolo:yolo zshrc        /home/yolo/.zshrc
COPY --chown=yolo:yolo zsh_aliases  /home/yolo/.zsh_aliases
COPY --chown=yolo:yolo tmux.conf    /home/yolo/.tmux.conf
COPY                  starship-extra.toml /tmp/starship-extra.toml
RUN install -d -o yolo -g yolo /home/yolo/.config \
    && starship preset plain-text-symbols -o /tmp/starship-base.toml \
    && cat /tmp/starship-base.toml /tmp/starship-extra.toml \
        > /home/yolo/.config/starship.toml \
    && chown yolo:yolo /home/yolo/.config/starship.toml \
    && rm /tmp/starship-base.toml /tmp/starship-extra.toml \
    && chsh -s /bin/zsh yolo

# SHELL=/bin/zsh exposes the chosen interactive shell to subprocesses (tmux,
# git, sub-shells) so they pick zsh as well.
# LC_NUMERIC=C keeps R / packaging / scripts using `.` as decimal separator
# regardless of LANG. Set at the Docker layer so even non-interactive shells
# (Rscript invoked from cron, scripts launched via `zsh -c`) inherit it; the
# .zshrc also exports it as a belt-and-braces for shells that bypass ENV.
ENV SHELL=/bin/zsh \
    LC_NUMERIC=C

# Restore the unprivileged default user from the upstream image so containers
# launched from this image keep dropping privileges by default.
USER yolo
WORKDIR /home/yolo