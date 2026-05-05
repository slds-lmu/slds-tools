# Install the core CRAN R packages baked into the slds-tools default image.
# Run from the Dockerfile via `Rscript install_cran.R`.
#
# Source: Posit Public Package Manager (PPM) binary tarballs for noble.
# install.packages downloads pre-compiled binaries and skips compilation;
# falls back to source build only when PPM hasn't yet built a given version.
#
# Failure handling: install.packages() emits a *warning* (not an error) when
# a package fails — the R process exits 0 either way. We post-check
# installed.packages() and stop() with non-zero exit so the docker build
# aborts at this layer instead of silently producing a broken image.

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
