---
title: "Podman Cheatsheet"
date: ""
author: ""
geometry:
  - a4paper
  - landscape
  - margin=14mm
header-includes:
  - \renewcommand{\normalsize}{\fontsize{7}{9}\selectfont}
  - \usepackage{titling}
  - \usepackage{titlesec}
  - \usepackage{ragged2e}
  - \usepackage{multicol}
  - \usepackage{enumitem}
  - \setlength{\columnsep}{12pt}
  - \setlength{\columnseprule}{0.2pt}
  - \setlist[itemize]{leftmargin=5mm,labelsep=1.5mm,after=\vspace{-0.6\baselineskip}}
  - \setlist{noitemsep,topsep=2pt}
  - \setlength{\droptitle}{-3em}
  - \titlespacing*{\subsection}{0pt}{0.25\baselineskip}{0.15\baselineskip}
  - \titlespacing*{\subsubsection}{0pt}{0.1\baselineskip}{0.1\baselineskip}
  - \titleformat{\subsection}{\normalfont\bfseries\fontsize{9pt}{11pt}\selectfont}{\thesubsection}{0.6em}{}
  - \posttitle{\par\end{center}\vspace{-5em}}
  - \AtBeginDocument{\begin{multicols}{3}\RaggedRight}
  - \AtEndDocument{\end{multicols}}
output: pdf_document
pdf-engine: xelatex
---

## Common option buckets (referenced below)

* **\[Output & filtering]**:
  `--format TEMPLATE` (Go‑template output), `--filter KEY=VALUE` (select by status/label/name, etc.), `-q/--quiet` (IDs only), `-a/--all` (include stopped), `-l/--latest` (last created object).

* **\[Auth & registries]**:
  `--authfile PATH` (use a specific auth file), `--creds USER:PASS` (inline credentials), `--tls-verify=BOOL` (enforce/skip TLS checks).

* **\[Interaction & TTY]** (containers):
  `-i/--interactive` (keep STDIN open), `-t/--tty` (allocate a TTY), `-u/--user UID[:GID]`, `-e/--env KEY=VAL`, `--env-file FILE`, `-w/--workdir DIR`.

* **\[Storage & mounts]** (containers):
  `-v SRC:DST[:OPTIONS]` (bind/volume mount; include `:ro`/`:rw`; on SELinux systems use `:z`/`:Z` to relabel), `--mount type=bind|volume|tmpfs,source=...,target=...`, `--tmpfs PATH[:OPTIONS]`, `--read-only` (root FS read‑only).

* **\[Networking]** (containers/pods):
  `-p HOST:CONT[/PROTO]` (publish a port), `-P/--publish-all` (publish all exposed), `--network bridge|host|none|NAME`, `--add-host HOST:IP`, `--dns IP`.

* **\[Security & isolation]** (containers):
  `--cap-add/--cap-drop CAP`, `--device /dev/…` (pass devices through), `--privileged` (all capabilities; disables some isolation), `--security-opt ...` (e.g., `label=disable`, `seccomp=unconfined`).

---

## Containers (lifecycle, exec, inspection)

* **`podman run [OPTIONS] IMAGE [COMMAND [ARG...]]`** — Create and start a new container.
  *Key options:* `-d/--detach` (run in background), `--name NAME` (set name), `--rm` (auto‑remove on exit), `--replace` (replace same‑name container), `--restart POLICY` (`no|on-failure[:N]|always`), `--pull=always|newer|missing|never` (image retrieval policy), plus \[Interaction & TTY], \[Storage & mounts], \[Networking], \[Security & isolation].

* **`podman create [OPTIONS] IMAGE [COMMAND [ARG...]]`** — Create a container without starting it (accepts almost all `run` options).

* **`podman start [--attach/-a] [--interactive/-i] CONTAINER...`** — Start one or more created/stopped containers; `-a` attaches to output, `-i` keeps STDIN open.

* **`podman stop [-t SECONDS] CONTAINER...`** — Gracefully stop containers with a timeout.

* **`podman restart [-t SECONDS] CONTAINER...`** — Stop and then start containers; honors restart policies on failure.

* **`podman kill [-s SIGNAL] CONTAINER...`** — Send a signal (default `SIGKILL`) to running containers.

* **`podman rm [-f] CONTAINER...`** — Remove containers; `-f` forces removal (kills first if needed).

* **`podman ps`** — List containers; use \[Output & filtering] to show all (`-a`), filter by `status=running`, or template fields.

* **`podman logs [OPTIONS] CONTAINER`** — Show container logs; `-f/--follow` streams logs, `--since TIME` limits by time, `--tail N` shows last *N* lines.

* **`podman exec [OPTIONS] CONTAINER COMMAND [ARG...]`** — Run a command inside a running container; commonly use \[Interaction & TTY] (`-it`), `-u`, `-e/--env`, and `-w`.

* **`podman attach CONTAINER`** — Attach your terminal to a running container’s STDIN/STDOUT/STDERR.

* **`podman cp SRC DEST`** — Copy files/folders between the host and a container (`container:/path` syntax).

* **`podman port [CONTAINER [PRIVATE_PORT[/PROTO]]]`** — Display port mappings for a container or a specific container port.

* **`podman inspect [--type container|image|pod|volume|network] NAME`** — Show low‑level JSON for an object; pair with `--format` to extract fields.

* **`podman stats [CONTAINER...]`** — Live resource usage; `--no-stream` prints a single snapshot.

* **`podman top CONTAINER [FORMAT...]`** — Show processes in a container; optional format descriptors (e.g., `pid,comm,etime`).

---

## Images (build, pull/push, list, import/export)

* **`podman pull [OPTIONS] IMAGE[:TAG|@DIGEST]`** — Download an image from a registry; typical options are \[Auth & registries].

* **`podman images`** — List local images; supports \[Output & filtering] (e.g., filter by `dangling=true`, template columns).

* **`podman rmi [-f] IMAGE...`** — Remove one or more images; `-f` removes even if referenced.

* **`podman tag SOURCE_IMAGE TARGET_IMAGE[:TAG]`** — Add a new tag pointing to an existing image.

* **`podman push [OPTIONS] IMAGE [DEST]`** — Upload an image to a registry or destination; use \[Auth & registries].

* **`podman save -o FILE [--format oci-archive|docker-archive] IMAGE[:TAG]`** — Export an image as a tar archive.

* **`podman load -i FILE`** — Import an image tarball created by `save` (or Docker).

* **`podman build [OPTIONS] [CONTEXT]`** — Build an image (Containerfile/Dockerfile) using Buildah under the hood.
  *Key options:* `-t NAME[:TAG]` (name the result), `-f FILE` (Dockerfile path), `--build-arg KEY=VAL`, `--target STAGE` (multi‑stage target), `--platform OS/ARCH` (build for a different platform), `--pull` (always try to pull bases), `--no-cache` (ignore build cache), `--squash` (squash layers).

* **`podman search TERM`** — Search registries for images; typically pair with `--filter` and `--limit`.

---

## Pods (group related containers with shared namespaces)

* **`podman pod create [--name NAME] [-p HOST:CONT]`** — Create a pod; `-p` publishes on the pod’s infra container and is shared by members.

* **`podman pod ps`** — List pods; supports \[Output & filtering].

* **`podman pod start|stop|rm NAME`** — Start/stop/remove pods as units.

* **`podman run --pod NAME ...`** — Join a container to an existing pod (inherits the pod’s network namespace and published ports).

---

## Volumes (named persistent storage)

* **`podman volume create [--label KEY=VAL] [--opt KEY=VAL] [NAME]`** — Create a named volume; `--opt` passes driver options (e.g., `type`, `device`, `o`).

* **`podman volume ls|inspect|rm|prune`** — List, examine, remove volumes; `prune` removes unused volumes.

---

## Networks

* **`podman network create [--subnet CIDR] [--gateway IP] [--label KEY=VAL] NAME`** — Create a user‑defined bridge network.

* **`podman network ls|inspect|rm|prune`** — Manage container networks; attach with `--network NAME` in `run/create`.

---

## Kubernetes & systemd integration

* **`podman generate systemd --name NAME [--files] [--new]`** — Emit systemd unit files for a container or a pod; `--files` writes `.service`/`.target` files, `--new` makes units create missing containers on start.

* **`podman generate kube NAME [--filename FILE]`** — Generate Kubernetes YAML for a container or a pod.

* **`podman play kube FILE [--replace]`** — Create/update containers and pods from Kubernetes YAML; `--replace` recreates changed resources.

---

## System housekeeping

* **`podman system prune [-a] [-f]`** — Remove unused data (containers, images, networks, volumes); `-a` includes unused images, `-f` skips confirmation.

* **`podman image|container|volume|network prune`** — Targeted pruning of a specific resource type.

* **`podman system df`** — Show disk usage by images, containers, and volumes.

* **`podman info`** — Display runtime, storage, and host details relevant to Podman.

* **`podman version`** — Print client/server (if applicable) and component versions.

---

## macOS/Windows virtualization (if applicable)

* **`podman machine init [NAME] [--cpus N] [--memory MB] [--disk-size GB]`** — Create the VM that runs containers.

* **`podman machine start|stop|ssh NAME`** — Manage or connect to the VM.

---

### Minimal legend (placeholders)

* `NAME` → a resource name (container/pod/network/volume).
* `IMAGE[:TAG]` → an image reference (defaults to `:latest`).
* `POLICY` → restart policy: `no`, `on-failure[:N]`, or `always`.
* `TEMPLATE` → Go template, e.g., `--format '{{.ID}} {{.Names}}'`.
* `TIME` → timestamp or relative duration, e.g., `--since 10m`.

---

**Summary:** learn `run` (with \[Interaction], \[Storage], \[Networking], \[Security]), `build`, `pull/push/tag`, `ps/logs/exec/inspect`, plus the pod/volume/network primitives; the rest are for export/import, automation (`generate systemd|kube`), and cleanup (`prune`).
