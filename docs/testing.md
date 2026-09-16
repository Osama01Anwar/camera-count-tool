# Testing

```powershell
uv run pytest                          # everything
uv run pytest -m "not gui"             # skip the Qt tests
uv run pytest --cov=camera_count --cov-report=term-missing
uv run python scripts/check_coverage.py coverage.xml
```

## What the layers are for

### Guards that fail the build

These are not ordinary tests. They exist so that a future change cannot quietly
undo a promise the project makes.

| Test | Promise |
|---|---|
| `test_forbidden_terms.py` | No estimation vocabulary anywhere in `src/`. The one permitted occurrence is the mandated disclaimer literal, allowed in exactly one module and checked by position |
| `test_no_network.py` | Walks the AST of every shipped module: no networking imports, no network calls, no `__import__("socket")` |
| `test_release_hygiene.py` | No mock-device code outside `tests/`, no `os.system`, no `shell=True`. It also tests the guard itself, so a guard that stops catching things is caught |
| `tests/core/test_models.py` | A `ShutterReading` cannot be constructed except through the factory, and only from a trusted, cited source |
| `tests/ptp/test_session.py` | Write operations are refused **before** they reach the transport, and the transport interface has no data-out parameter at all |
| `tests/adapters` | Every adapter's vendor allow-list is empty until a citation justifies an entry |
| `tests/db` | SQL `CHECK` constraints refuse a stored count with no source |

### Property-based fuzzing

`tests/ptp/test_fuzz.py` throws arbitrary bytes at every parser and asserts the
contract: return a value, or raise `ParseError`. Never anything else, never a
hang, and never an allocation sized by a number the device chose.

### Unit tests

Ordinary coverage of parsing, registry loading and validation, firmware ranges,
originality checks, field lookup, report rendering and CLI behaviour.

### Integration against real camera files

`tests/metadata/test_real_samples.py` runs against the sample images that ship
with the ExifTool distribution. They prove what unit tests cannot: that the
identifiers in the registry are the strings ExifTool actually produces for a
real file from that camera - a Nikon D70 reading 3619, a Pentax K10D reading
1648 after decryption.

They skip unless the distribution has been fetched:

```powershell
uv run python scripts/fetch_exiftool.py --mode source
```

### GUI smoke tests

`tests/gui/` uses pytest-qt with `QT_QPA_PLATFORM=offscreen`. They check that a
count appears with its source, that an unavailable count says so plainly, and
that no hedging vocabulary reaches the screen.

## Coverage floors

Per package, not one repository-wide number, because coverage matters most in
the code that decides whether a number is shown at all:

| Package | Floor |
|---|---|
| `core` | 90% |
| `ptp` | 85% |
| `adapters` | 85% |
| `metadata` | 85% |
| `registry` | 85% |

`scripts/check_coverage.py` enforces them and CI runs it.

## Markers

- `gui` - needs Qt. Runs headless in CI.
- `hardware` - needs a physically connected camera. Never run in CI.

## Adding a test for a camera

Do not add a test that asserts a particular camera returns a particular number
unless you have a fixture that makes it reproducible. Prefer an ExifTool JSON
fixture under `tests/fixtures/`, with the serial number redacted.
