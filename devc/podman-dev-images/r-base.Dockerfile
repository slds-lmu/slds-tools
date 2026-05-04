ARG TAG=latest
FROM rocker/r-ver:${TAG}

ENV DEBIAN_FRONTEND=noninteractive

# Base tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git openssh-client gnupg \
    build-essential pkg-config \
    python3 python3-venv python3-pip \
    ripgrep jq unzip zip rsync less vim nano \
    procps sudo fzf zsh man-db gh aggregate \
    tmux htop parallel tini \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG NODE_MAJOR=20
RUN mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && chmod a+r /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get clean && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /usr/local/share/npm-global

ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=/usr/local/share/npm-global/bin:$PATH

# Enable corepack (ships with Node >= 16)
RUN corepack enable

# Sanity check (visible in build logs)
RUN node --version && npm --version

# git-delta
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) \
 && wget -O /tmp/git-delta.deb \
      "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" \
 && dpkg -i /tmp/git-delta.deb \
 && rm /tmp/git-delta.deb

# Global npm CLIs
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

ARG CODEX_VERSION=latest
RUN npm install -g @openai/codex@${CODEX_VERSION}

# Additional packages for R dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev libcurl4-openssl-dev zlib1g-dev libfontconfig1-dev \
    libharfbuzz-dev libfribidi-dev libfreetype6-dev libpng-dev \
    libtiff5-dev libjpeg-dev libxml2-dev libeigen3-dev cmake \
    libgit2-dev libx11-dev pandoc libglpk-dev \
    libudunits2-dev libhiredis-dev libproj-dev libprotobuf-dev \
    libgdal-dev \
    tidy texlive texlive-latex-extra texlive-fonts-extra texlive-xetex qpdf \
    latexmk texlive-extra-utils texlive-bibtex-extra biber \
    texlive-lang-european texlive-lang-german texlive-lang-english lmodern texlive-science \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Miniforge
ARG MINIFORGE_VERSION=24.7.1-0
RUN if [ "${MINIFORGE_VERSION}" = "latest" ]; then \
      pathx="latest/download"; \
    else \
      pathx="download/${MINIFORGE_VERSION}"; \
    fi \
 && curl -fsSL -o /tmp/miniforge.sh \
      "https://github.com/conda-forge/miniforge/releases/${pathx}/Miniforge3-${MINIFORGE_VERSION}-Linux-$(uname -m).sh" \
 && bash /tmp/miniforge.sh -b -p /opt/conda \
 && rm -f /tmp/miniforge.sh \
 && /opt/conda/bin/conda clean -afy \
 && /opt/conda/bin/conda install -n base -y mamba \
 && /opt/conda/bin/conda clean -afy \
 && chown -R root:root /opt/conda && chmod -R 755 /opt/conda

# System-wide Conda config: put envs and pkgs on a single persistent mount
RUN mkdir -p /etc/conda \
 && printf '%s\n' \
    'channels:' \
    '  - conda-forge' \
    'channel_priority: strict' \
    'auto_update_conda: false' \
    'auto_activate_base: false' \
    'envs_dirs:' \
    '  - /home/dev/conda/envs' \
    'pkgs_dirs:' \
    '  - /home/dev/conda/pkgs' \
    > /etc/conda/condarc \
 && echo '. /opt/conda/etc/profile.d/conda.sh' >> /etc/bash.bashrc
# Make Conda available in every interactive shell without touching user dotfiles

ARG HQ_VERSION=latest
RUN case "$(uname -m)" in \
      x86_64)  arch="amd64" ;; \
      aarch64) arch="arm64" ;; \
      ppc64le) arch="ppc64le" ;; \
      *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac \
 && case "$arch" in \
      amd64)  asset_arch="x64" ;; \
      arm64)  asset_arch="arm64" ;; \
      ppc64le) asset_arch="ppc64" ;; \
      *) echo "Unsupported TARGETARCH: $arch" >&2; exit 1 ;; \
    esac \
 && repo="It4innovations/hyperqueue" \
 && if [ "$HQ_VERSION" = "latest" ]; then \
      api="https://api.github.com/repos/${repo}/releases/latest"; \
    else \
      v="${HQ_VERSION#v}" \
   && api="https://api.github.com/repos/${repo}/releases/tags/v${v}"; \
    fi \
 && json="$(curl -fsSL --retry 5 --retry-connrefused --retry-delay 2 "$api")" \
 && url="$(printf '%s' "$json" | jq -r --arg a "linux-${asset_arch}" \
        '.assets[]\
         | select(.name | startswith("hq-"))\
         | select(.name | contains($a))\
         | select(.name | endswith(".tar.gz"))\
         | .browser_download_url' \
      | head -n1)" \
 && [ -n "$url" ] \
 && curl -fsSL --retry 5 --retry-connrefused --retry-delay 2 "$url" -o /tmp/hq.tar.gz \
 && sha_url="$(printf '%s' "$json" | jq -r --arg n "$(basename "$url")" \
        '.assets[]\
         | select(.name == ($n + ".sha256"))\
         | .browser_download_url' \
      | head -n1)" \
 && if [ -n "$sha_url" ]; then \
      curl -fsSL --retry 5 --retry-connrefused --retry-delay 2 "$sha_url" -o /tmp/hq.sha256 \
   && expected="$(awk '{print $1}' /tmp/hq.sha256)" \
   && echo "${expected}  /tmp/hq.tar.gz" | sha256sum -c -; \
    fi \
 && mkdir -p /tmp/hq-extract \
 && tar -xzf /tmp/hq.tar.gz -C /tmp/hq-extract \
 && install -m 0755 /tmp/hq-extract/hq /usr/local/bin/hq \
 && rm -rf /tmp/hq.tar.gz /tmp/hq.sha256 /tmp/hq-extract \
 && hq --version


# Non-root default user
RUN groupadd -g 1000 dev \
 && useradd -m -u 1000 -g 1000 -s /bin/zsh dev \
 && mkdir -p /home/dev/.cache \
 && chown dev:dev /home/dev/.cache


# Dotfiles (ensure correct ownership)
COPY --chown=dev:dev .zshrc .gitconfig .gitignore_global .tmux.conf r-tools /home/dev/

RUN mkdir -p /home/dev/.cache/R \
 && chown dev:dev /home/dev/.cache/R \
 && echo '. /opt/conda/etc/profile.d/conda.sh'>> /home/dev/.zshrc

WORKDIR /workspace
ENV SHELL=/bin/zsh \
    EDITOR=vim \
    VISUAL=vim \
    DEVCONTAINER=true \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CONFIG_DIR=/home/dev/.claude \
    R_LIBS= \
    R_LIBS_SITE=/usr/local/lib/R/site-library:/usr/local/lib/R/library

USER dev
