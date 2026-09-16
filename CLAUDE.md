# Project conventions - Camera Count Tool

Read this before changing anything. The rules below are not style preferences;
several of them are enforced by tests that fail the build.

## The one rule

**Exact data or no data.** Output is binary: `VERIFIED EXACT COUNT` with an
integer from a cited authoritative source, or `EXACT COUNT UNAVAILABLE` with a
reason. Reporting unavailable is a correct, successful result. Never soften it.

## Hard prohibitions (enforced in code and tests)

Never display, store as a shutter count, or derive a count from:

- image numbers, file names or sequences, timestamps, photo counts on a card, frame or video counters
- estimation, extrapolation, interpolation, statistics, or any AI/ML
- confidence scores, or the words *estimated, approximate, probably, likely, % confidence*
- arithmetic across counters (mechanical + electronic = total) unless the manufacturer documents that relation
- any metadata field not listed in the verified field registry for that exact model

`tests/test_forbidden_terms.py` greps `src/` for `estimat`, `approx`, `probab`,
`confidence`, `likely` and fails the build. The single allowed occurrence is
`NO_ESTIMATE_DISCLAIMER` in `src/camera_count/core/messages.py`; import it, never
retype it.

If a non-authoritative counter appears in the data, surface it with
`messages.IMAGE_COUNTER_NOTICE` and put its value in a
`NonAuthoritativeCounter`, never in a counter slot.

## Construction guard

`ShutterReading` can only be built by `ShutterReading.from_source(value=...,
source_id=...)`. The factory resolves the id through the registry and refuses
anything whose `verification_status` is not `documented` or
`hardware_verified`. Direct construction raises `ForbiddenConstructionError`.
Do not add another constructor, do not relax the guard for tests - use the
`documented_source` fixture.

## Read-only guarantee

The software must never change settings, release the shutter, delete or modify
files, format media, touch firmware, reset counters, or write service data.

Every adapter declares `allowed_opcodes: frozenset[int]`. The PTP session checks
the opcode against that set **before** sending, and raises
`ForbiddenOperationError` otherwise. Data-out phases are forbidden except the
command container itself. Files are opened read-only.

## Citations

Never invent PTP opcodes, property codes, MakerNotes tag IDs, or model support.
Every registry method carries a `citation` that is either a URL or a
`repo/path:line` reference. If no citable source exists, the model is
`exact_count_available: false`. `hardware_verified` additionally requires a row
in `docs/hardware-test-matrix.md`.

## Offline

No network calls anywhere in `src/`. `tests/test_no_network.py` walks the AST of
every shipped module and fails on networking imports or calls. Build scripts
under `scripts/` and `packaging/` may download pinned artifacts; shipped code
may not.

## Untrusted input

Camera bytes and file bytes are hostile until parsed. Bound every read, check
lengths before every slice, cap array counts, enforce timeouts on USB and
subprocess calls, and never `eval`, `exec`, or `shell=True`. Parsers get
Hypothesis fuzz tests.

## Layout

```
src/camera_count/
  core/        models, guards, fixed messages, errors
  usb/         per-OS enumeration
  ptp/         containers, transports, session, allow-list
  adapters/    one module per manufacturer
  metadata/    ExifTool runner, original-file checks, field registry
  registry/    camera_database/*.yaml + schema + loader
  db/          SQLite schema, migrations, repository
  report/      report builders
  cli/  gui/  diagnostics/
```

Files stay under 800 lines, functions under 50, nesting under 4 levels. Many
small cohesive modules beat few large ones. Prefer immutable frozen dataclasses;
build new objects instead of mutating.

## Mocks

Mock devices live only in `tests/devmock/`. The `--dev-mock` flag appears only
when that package is importable and `CAMERA_COUNT_DEV` is set.
`packaging/verify_release.py` fails the build if any of it reaches a
distribution. Mock output is labelled `MOCK CAMERA - TEST ONLY`. Never use
realistic-looking example counts in production UI or docs screenshots.

## Workflow

Run before every commit:

```bash
ruff check . && ruff format --check .
mypy
pytest
```

Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`,
`perf:`, `ci:`). Coverage target: 85% on `core`, `ptp`, `adapters`, `metadata`.

## Priority when rules conflict

accuracy > safety (read-only) > coverage > features.
