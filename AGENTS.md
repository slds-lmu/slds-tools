# AGENTS

Conventions for AI agents (and humans) working in this repo.

## Subprojects have their own CLAUDE.md

This repo is an umbrella for several distinct tools. When working in a
subdirectory that has its own `CLAUDE.md` (e.g. `publs/CLAUDE.md`),
*that* file is the contract for the subproject — read it first and
defer to it on conflicts with this file.

## Rule: document all config files and scripts

Every config file or script must be documented.

1. Header comment at the top of the file stating the purpose of the file
2. For functions, doc purpose, inputs, outputs, and side-effects
3. In config files, doc the purpose of each config option

## Working agreements

- **Default to terse.** Design docs are kept very short
  (`architecture.md`-style files target ~40 lines, list-shaped). Halve
  a doc when in doubt about length.
- **Propose before tearing down.** A "rework completely" instruction
  does not authorise deleting big swaths of code without confirmation.
  Surface 2-3 clarifying questions that shape the rewrite first.
- **Reverse recent decisions cleanly.** When better framing arrives,
  cut recent code without ceremony — don't preserve it for
  "compatibility" or "support both modes". (Hard-fail vs skip+warn was
  a clean reversal; do that, not a hybrid.)
- **Don't over-engineer.** Smallest thing that works. Cut auto-resolver
  scripts, fallback chains, "future-proofing" abstractions unless the
  requirement is real today.
- **Iterative, not big-bang.** Do step 1, show the result, then step 2.
  Don't try to land a multi-hour implementation in one turn.
- **Per-subproject contracts override these.** Anything in a subproject's
  `CLAUDE.md` wins over the working agreements above when they conflict.
