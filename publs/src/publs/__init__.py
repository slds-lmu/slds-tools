"""publs — maintain a single SSOT BibTeX file for SLDS publications.

Layers:
    config   -> Settings + MemberList from YAML
    bibdb    -> load / index / append the SSOT slds.bib
    sources/ -> external publication sources (openalex; crossref/scholar TBD)
    match    -> "is this candidate already in the SSOT?"
    review   -> interactive accept/reject loop
    cli      -> click app exposed as `publs`
"""

__version__ = "0.2.0"
