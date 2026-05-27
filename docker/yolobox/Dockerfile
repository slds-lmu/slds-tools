FROM ghcr.io/finbarr/yolobox:latest

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Locale data (en_US.UTF-8 generated below; LANG/LC_ALL stay C.UTF-8)
    locales \
    # Extra shell utilities (from slds-tools)
    procps \
    man-db \
    aggregate \
    tmux \
    parallel \
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

# LaTeX / document toolchain (from slds-tools). texlive-full pulls ~3000 .deb
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

# Python ML stack (from slds-tools). Ubuntu 24.04 ships a PEP 668 marker that
# blocks system-wide `pip install` outside a venv; we remove it because this
# is a single-purpose container that doesn't need PEP 668's host protection.
RUN rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED \
    && pip install --no-cache-dir \
        numpy \
        pandas \
        scikit-learn \
        matplotlib \
        jupyter

# Playwright + Chromium (from slds-tools). --with-deps invokes apt to install
# the OS-level libraries Chromium needs to run headless.
RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

# air: Posit's R formatter (Rust binary). The cargo-dist installer drops the
# binary at /root/.local/bin/air; move it to /usr/local/bin so every user
# finds it on PATH, then strip the rc-file edits the installer leaves behind.
RUN curl -LsSf https://github.com/posit-dev/air/releases/latest/download/air-installer.sh | sh \
    && mv /root/.local/bin/air /usr/local/bin/air \
    && rm -rf /root/.local /root/.config/air \
    && sed -i '/\.local\/bin\/env/d' /root/.zshrc /root/.bashrc /root/.profile 2>/dev/null || true