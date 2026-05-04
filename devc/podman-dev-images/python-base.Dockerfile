ARG TAG=latest

FROM devc/base:${TAG}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH=/home/dev/.local/bin:$PATH \
    UV_LINK_MODE=copy

