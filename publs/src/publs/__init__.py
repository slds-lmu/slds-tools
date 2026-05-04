"""publs — scrape SLDS member publications from Google Scholar into BibTeX.

Three layers, all driven by two YAML files (config.yaml + members.yaml):

    config   ->  parses YAML into Settings + Member dataclasses
    scholar  ->  hits Google Scholar via `scholarly`, writes a JSON cache
    bibtex   ->  reads the JSON cache, applies filters, writes one .bib per
                 member

The `cli` module wires these together as a `click` app exposed as `publs`.
"""

__version__ = "0.1.0"
