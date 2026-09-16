## What this changes

<!-- One or two sentences. -->

## Type

- [ ] New camera model or method (requires a citation)
- [ ] Bug fix
- [ ] Feature or refactor
- [ ] Documentation
- [ ] Build or CI

## If this adds or changes a camera method

- [ ] Every method carries a citation: a URL, or `repo/path:line`
- [ ] The citation says what the entry claims - including the counter type
- [ ] `verification_status` is `documented`, unless a hardware test row is included
- [ ] `hardware_verified` entries have a row in `docs/hardware-test-matrix.md`
- [ ] A fixture is included, with the serial number redacted
- [ ] `docs/manufacturer-support.md` has been regenerated

**Citation:**

```
<!-- paste the reference, and quote what the source actually says -->
```

## Checks

- [ ] `ruff check .` and `ruff format --check .`
- [ ] `mypy`
- [ ] `pytest`
- [ ] Coverage floors still met (`scripts/check_coverage.py`)

## The rules this project does not bend

- [ ] Nothing here makes the tool produce a number it cannot justify
- [ ] Nothing here writes to a camera
- [ ] Nothing here adds a network call
- [ ] No mock or test code can reach a release
