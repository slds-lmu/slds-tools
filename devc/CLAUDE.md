# CLAUDE.md — devc

Rules of engagement for any agent (or teammate) modifying this
subproject. Read alongside the subproject's own `README.md` and
`specs.md`.

## Working agreements (repo-wide)

Duplicated in each subproject's `CLAUDE.md`. The repo has no top-level
CLAUDE.md, by design — Claude Code only auto-loads `CLAUDE.md` from
the launch CWD.

- **Document all config files and scripts.** (1) Header comment stating
  the purpose of the file; (2) for functions, doc purpose, inputs,
  outputs, side-effects; (3) in config files, doc the purpose of each
  option.
- **Default to terse.** Design docs are kept very short
  (`architecture.md`-style files target ~40 lines, list-shaped). Halve
  a doc when in doubt about length.
- **Propose before tearing down.** A "rework completely" instruction
  does not authorise deleting big swaths of code without confirmation.
  Surface 2-3 clarifying questions that shape the rewrite first.
- **Reverse recent decisions cleanly.** When better framing arrives,
  cut recent code without ceremony — don't preserve it for
  "compatibility" or "support both modes".
- **Don't over-engineer.** Smallest thing that works. Cut auto-resolver
  scripts, fallback chains, "future-proofing" abstractions unless the
  requirement is real today.
- **Iterative, not big-bang.** Do step 1, show the result, then step 2.
  Don't try to land a multi-hour implementation in one turn.
