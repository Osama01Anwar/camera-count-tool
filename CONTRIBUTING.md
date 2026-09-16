# Contributing

Thank you for helping. The most valuable contribution to this project is a
**citation**, not code: a documented, verifiable way to read an exact counter
from a specific camera model.

## Ground rules

Read [CLAUDE.md](CLAUDE.md) first. It lists the prohibitions that are enforced
by tests. In short: no estimation, no invented opcodes or tag IDs, no writes to
the camera, no network calls, and every number must trace to a source.

A pull request that makes the tool guess will be closed, however accurate the
guess happens to be.

## Development setup

```bash
git clone https://github.com/Osama01Anwar/camera-count-tool
cd camera-count-tool
uv venv --python 3.12
uv pip install -e ".[dev]"

ruff check . && ruff format --check .
mypy
pytest
```

See [docs/building.md](docs/building.md) for packaging and
[docs/testing.md](docs/testing.md) for the test layers.

## Adding a camera model

Full walkthrough: [docs/adding-camera-model.md](docs/adding-camera-model.md).
Summary of what a PR must contain:

1. A registry entry in `src/camera_count/registry/camera_database/<make>.yaml`.
2. A **citation** for every method - a URL to manufacturer or protocol
   documentation, or a `repo/path:line` reference into a public source tree such
   as an ExifTool tag table or libgphoto2's PTP definitions.
3. `verification_status: documented` at most. Only a maintainer merging a
   hardware test can set `hardware_verified`, and only together with a row in
   [docs/hardware-test-matrix.md](docs/hardware-test-matrix.md).
4. A fixture: a recorded, redacted PTP transaction or an ExifTool JSON output,
   under `tests/fixtures/`.

Do not submit a model because a tool you used once showed a number. Submit it
because you can point at where that number is documented.

## Hardware verification

The procedure is performed by a human, on the camera:

1. Read the count with `camera-count count`.
2. Press the shutter N times **on the camera** - the software never triggers it.
3. Read again and confirm the count increased by exactly N.
4. Where possible, compare against a manufacturer service reading.
5. Add a matrix row with camera, firmware, OS, connection, method, citation,
   before/after readings, date, tester, and status.

## Commits and PRs

Conventional Commits. Keep the diff focused. CI must be green: ruff, mypy,
pytest on Windows, macOS and Linux, plus the packaging job.

## Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
