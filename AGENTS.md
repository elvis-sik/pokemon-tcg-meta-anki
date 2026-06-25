# Repository Instructions

This repository builds a reproducible Anki package for competitive Pokemon TCG study cards from the frozen 2026-06-25 handoff data.

## Project Shape

- Treat files under `data/`, `schemas/`, `templates/`, and the handoff documentation as source inputs unless a task explicitly changes the source snapshot.
- Treat `generated/`, `media/`, `cache/`, `reports/`, and `dist/` outputs as reproducible build artifacts unless their README or a task says otherwise.
- Preserve stable natural keys and mechanical identity rules from `HANDOFF_PROMPT.md` and `MECHANICAL_IDENTITY.md`.
- Do not force output counts to earlier planning estimates; report audited counts instead.

## Development

- Prefer `make test` for local tests and `make validate-source` for frozen input validation.
- Network-dependent commands are separate by design. Run resolver and media steps only when the task requires live data or refreshed cache.
- Use Socket Firewall (`sfw`) for public package-registry installs or dependency resolution.
- Keep dependency resolution constrained to releases at least 7 days old where the toolchain supports it.
