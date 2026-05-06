# Install the R packages baked into the slds-tools default image.
# Run from the Dockerfile via `Rscript install_packages.R`.
#
# Uses pak to resolve and install binary packages across PPM + r-universe.
#
# Repository policy:
#   - PPM (Posit Public Package Manager): primary CRAN mirror, serving
#     pre-compiled noble binaries from a date-pinned snapshot (not `latest`).
#     Bump the date below to pick up newer R packages; see README for the
#     full rationale and bump procedure.
#   - mlr-org.r-universe.dev: r-universe binaries for the latest mlr3
#     development releases (often ahead of CRAN). No date pin available.
#   - community.r-multiverse.org: r-universe binaries for community packages
#     not yet (or never) on CRAN. No date pin available.
# We deliberately do NOT add a source-only fallback like cloud.r-project.org —
# all three repos serve binaries, so pak resolves only binary candidates and
# any "package missing on Linux noble" condition surfaces as a hard pak error
# rather than a slow source-compile attempt that may also fail.
#
# Failure handling: pak::pak() raises a hard error (non-zero R exit) on
# resolution / install failure, but we still post-check installed.packages()
# defensively so a future pak release that downgrades errors to warnings
# still trips this layer.

Sys.setenv(NOT_CRAN = "true")
install.packages(
    "pak",
    repos = sprintf(
        "https://r-lib.github.io/p/pak/stable/%s/%s/%s",
        .Platform$pkgType, R.Version()$os, R.Version()$arch
    )
)
pak::repo_add(
    PPM          = "https://packagemanager.posit.co/cran/__linux__/noble/2026-05-05",
    mlr3universe = "https://mlr-org.r-universe.dev",
    multiverse   = "https://community.r-multiverse.org"
)
pkgs <- c(
    # --- general data-science / dev toolkit ---
    "tidyverse",    # tidyverse: meta-pkg of dplyr/ggplot2/tidyr/readr — standard toolkit
    "data.table",   # data.table: fast in-memory tabular data manipulation
    "ggplot2",      # ggplot2: grammar-of-graphics plotting (also bundled in tidyverse)
    "knitr",        # knitr: dynamic report generation (Rnw / Rmd weaving)
    "devtools",     # devtools: package-development helpers (install_github, document, check)
    # --- mlr3 ecosystem ---
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
