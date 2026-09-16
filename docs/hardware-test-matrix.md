# Hardware test matrix

A model is `hardware_verified` only when it appears here. Every row records a
test a person performed on a physical camera.

## The procedure

1. Connect the camera, or take an original file from it, and read the count.
2. **Press the shutter N times yourself, on the camera.** The software never
   triggers a shutter, and never will.
3. Read the count again.
4. Confirm that `after - before` equals exactly N.
5. Where possible, compare against a manufacturer service reading.
6. Add a row below, and open a pull request with a redacted fixture.

If the difference is not exactly N, that is a finding worth recording too: add
the row with status `mismatch` and describe what happened. A counter that does
not count what we think it counts is exactly what this matrix exists to catch.

## Matrix

| Manufacturer | Model | Firmware | OS | Connection | Method | Citation | Before | Presses | After | Date | Tester | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| _(none yet)_ | | | | | | | | | | | | |

No model has been hardware-verified yet. Every registered method currently
carries the status `documented`, which means a public source defines the field
but no one has confirmed on a body that it increments as expected.

## Reading a row

- **Method** - `makernote_field`, `ptp_property` or `ptp_operation`, matching
  the registry entry.
- **Citation** - the same reference the registry entry carries.
- **Status** - `verified` when the difference matched exactly, `mismatch` when
  it did not, `partial` when only some counters behaved.

## Recording a test locally

The local database can hold your test while you prepare the pull request, and
it enforces the arithmetic:

```python
from camera_count.db import Database

Database().record_verification(
    manufacturer="Nikon",
    model="NIKON Z 6_2",
    source_id="nikon/#0",
    reading_before=12345,
    presses=10,
    reading_after=12355,
    firmware="1.40",
    tester="your name or handle",
)
```

A row whose `after - before` does not equal `presses` is stored with
`matched = 0` - it cannot be recorded as a success.
