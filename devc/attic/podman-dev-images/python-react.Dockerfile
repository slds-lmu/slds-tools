ARG TAG=latest

FROM devc/base:${TAG}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH=/home/dev/.local/bin:$PATH \
    UV_LINK_MODE=copy

USER root

ARG PW_VERSION=latest

# Install browsers to a shared, fixed path and keep that path at runtime.
# (This is how the official image behaves.)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_GC=1

# 1) Install OS deps + browsers in one layer (requires root).
RUN npx -y playwright@${PW_VERSION} install --with-deps \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

USER dev
