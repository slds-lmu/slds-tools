# Installing MinerU into the SLDS default Docker image

Assessment of the effort needed to bake [MinerU](https://github.com/opendatalab/MinerU)
(OpenDataLab's PDF / Office → Markdown / JSON converter) into
`docker/default/Dockerfile`.

## TL;DR

**Difficulty: low-to-medium for the CPU pipeline backend, medium-to-high
for the full VLM stack.**

For CPU-only use (`pipeline` backend) it's basically:

- 4 extra apt packages (3 of which are fonts),
- one `pip install` line,
- optionally a model pre-download step that adds a few GB to the image.

The hard parts aren't the install itself — they're (1) deciding whether
to ship the ~1-3 GB of model weights inside the image vs downloading on
first run, and (2) whether you ever want the high-accuracy VLM backend,
which assumes a CUDA-capable GPU and is a different conversation.

## What MinerU is

A document-parsing engine: PDFs, DOCX/PPTX/XLSX, and images → Markdown /
JSON, with formulas converted to LaTeX, tables to HTML, multi-column
layouts handled, and OCR for scanned input. 109 languages.

Two backends:

- **`pipeline`** — classical CV/OCR stack, CPU-friendly (4 GB VRAM
  minimum if a GPU is present, but pure CPU works). Quoted accuracy
  ~85+.
- **`vlm`** — vision-language model backend, requires Volta+ NVIDIA GPU
  with 8 GB+ VRAM (or Apple Silicon). Quoted accuracy 95+.

The official Docker image bases on `vllm/vllm-openai:v0.11.2` — i.e. it
assumes GPU. Our `docker/default` image is CPU-oriented, so the natural
fit is the `pipeline` backend.

## Compatibility with our base image

`docker/default/Dockerfile` is Ubuntu 24.04 + Python 3.12 + the PEP-668
marker already deleted, so `pip install` writes system-wide. MinerU
supports Python 3.10-3.13, so 3.12 is fine.

Resource expectations from upstream:

| Resource | MinerU minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB+ |
| Disk | 20 GB | SSD |

These are run-time requirements for users of the image, not build-time
constraints — relevant for whoever runs the container, not for the
build host.

## Concrete changes to `docker/default/Dockerfile`

### 1. apt packages (small)

MinerU's own Dockerfile installs:

- `libgl1` — OpenCV runtime, used by the OCR stack.
- `fonts-noto-core`, `fonts-noto-cjk` — needed so rendered PDFs/Office
  docs have glyphs for CJK and miscellaneous Unicode.
- `fontconfig` — font cache; we already pull this in transitively via
  R's `libfontconfig1-dev`, but the `fontconfig` *binary* package is
  what MinerU wants. Cheap to add.

Optionally `libreoffice` if you want headless conversion of `.docx /
.pptx / .xlsx` to PDF before parsing — adds ~500 MB. Skip unless you
actually need Office input.

This is one extra apt block (or appended to the existing
"Developer tools" block).

### 2. pip install (one line)

```Dockerfile
RUN pip install --no-cache-dir -U "mineru[core]"
```

`mineru[core]` is the CPU-pipeline-capable extra. `mineru[all]` pulls
the VLM backend (sglang, torch with CUDA wheels, …) and is heavyweight
— avoid unless you've decided to ship the GPU path.

We already have a `pip install` layer; one more line.

### 3. Model weights — the actual decision point

MinerU needs model files (layout detection, OCR, formula recognition,
table structure). Two ways:

**(a) Bake them in.** Add:

```Dockerfile
RUN mineru-models-download -s huggingface -m all \
 && export MINERU_MODEL_SOURCE=local
ENV MINERU_MODEL_SOURCE=local
```

- Pro: container works fully offline, first run is fast.
- Con: image grows by an estimated ~1-3 GB (pipeline-only models;
  `-m all` may pull more). Pushes the image meaningfully larger.
- Con: pins a model snapshot to the image build date.

**(b) Lazy download.** Don't pre-fetch. First time a user calls
`mineru`, it downloads to `~/.cache/` (or wherever the env var points).
Smaller image, slower first run, requires network access at run time.

Given the umbrella nature of the image (general-purpose lab container,
already pretty fat from `texlive-full`), **option (b) is probably
right** unless offline reproducibility matters to you. The `texlive-full`
layer already pushes the image past 5 GB; adding another 1-3 GB of
models that not every user needs is questionable.

### 4. Optional: pin model source

The upstream Dockerfile sets `MINERU_MODEL_SOURCE=local`. If you go
with lazy download you'd instead leave this unset (defaults to
HuggingFace) or explicitly set it to `huggingface` or `modelscope`
(China-friendly mirror).

## Estimated effort

| Step | Time | Risk |
|---|---|---|
| Add apt packages | 5 min | trivial |
| Add `pip install "mineru[core]"` | 5 min | low — could conflict with our existing numpy / torch-free stack, easy to spot in `docker build` |
| Decide on model pre-fetch | 15 min discussion | the actual judgement call |
| Pre-fetch models (if chosen) | 1 build cycle | size blow-up, slow build |
| Smoke test (`mineru -p sample.pdf -o /tmp/out`) | 10 min | should just work on CPU |

**Total: under an hour of work, plus one or two `docker build` cycles
to verify.** The biggest variable is build time — pulling MinerU's
dependency tree (PaddleOCR / RapidOCR style stack, plus PyTorch CPU
wheels if `[core]` brings them) adds non-trivial layer time.

## Risks and footguns

1. **Image size.** Even without model weights, `mineru[core]` pulls a
   sizeable Python dependency tree (OCR, layout, image processing).
   `mineru[all]` is much worse. Check `docker image ls` deltas before
   committing.
2. **Torch CPU wheels.** If MinerU's deps drag in CPU-only PyTorch
   (~500 MB), that's fine but worth noting. If they drag in the CUDA
   wheels by default, force CPU wheels with
   `pip install --index-url https://download.pytorch.org/whl/cpu` or
   constrain via `--extra-index-url`. Verify what `mineru[core]`
   actually resolves to before merging.
3. **No GPU available in `docker/default`.** The `pipeline` backend is
   fine; the `vlm` backend will not run. Don't promise users 95+
   accuracy from this image.
4. **PEP 668 already disabled** in our image (`EXTERNALLY-MANAGED`
   removed), so we don't need MinerU's `--break-system-packages` hack.
5. **Office input via LibreOffice.** If users want `.docx → md`, add
   `libreoffice` (or `libreoffice-core` for ~half the size). PDFs and
   images work without it.
6. **First-run network access** if you go with lazy model download —
   the container needs to reach HuggingFace. In air-gapped or
   firewalled setups this fails surprisingly; pre-baking models is
   safer there.

## Suggested minimal diff (CPU-only, lazy models)

Append to the existing "Developer tools" or "Scientific libraries"
section, then add a small pip layer near the existing Python ones:

```Dockerfile
# --- MinerU runtime deps (libgl + fonts for OCR / PDF rendering) ------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        fontconfig \
        fonts-noto-core \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# --- MinerU (CPU pipeline backend; models lazy-downloaded on first run) -----
RUN pip install --no-cache-dir -U "mineru[core]"
```

That's the entire change for the "easy" path. If models-in-image is
desired, add one more `RUN mineru-models-download …` layer and an `ENV
MINERU_MODEL_SOURCE=local`.

## Recommendation

If you actually have a use case (e.g. converting lecture PDFs to
markdown for downstream tooling), add the CPU `pipeline` variant with
lazy model download — it's a ~10-line patch and doesn't materially
change image size until first use. Hold off on `mineru[all]` and on
baking models unless you have a concrete reason; both decisions are
reversible later.

If MinerU is going to be used by enough projects that pre-baking models
makes sense, that's the moment to consider a *separate* image
(`docker/mineru/`) parallel to `docker/yolobox/`, rather than bloating
`docker/default/`.

## Sources

- [MinerU repo (opendatalab/MinerU)](https://github.com/opendatalab/MinerU)
- [Official Dockerfile (docker/global/Dockerfile)](https://github.com/opendatalab/MinerU/blob/master/docker/global/Dockerfile)
- [Quick start docs](https://opendatalab.github.io/MinerU/quick_start/)
- [Docker deployment docs](https://opendatalab.github.io/MinerU/quick_start/docker_deployment/)
- [FAQ](https://opendatalab.github.io/MinerU/faq/)
