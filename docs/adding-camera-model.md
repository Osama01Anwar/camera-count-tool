# Adding a camera model

The most valuable contribution to this project is a citation. Code that reads a
field is easy; knowing which field, for which model, and being able to prove it,
is the hard part.

## What you need before you start

**A source.** A public document or source file that says this field or
operation is the actuation counter for this model. Good sources:

- An ExifTool tag table: `exiftool/lib/Image/ExifTool/<Make>.pm:<line>`
- libgphoto2's PTP definitions: `libgphoto2/camlibs/ptp2/ptp.h:<line>`
- Manufacturer documentation, protocol specifications, or an SDK header
- A Windows SDK header for platform constants

What is not a source: a forum post asserting a number without evidence, another
tool's output, or a value you found by trying codes until one returned something
plausible.

## Finding candidates

```powershell
python scripts/fetch_exiftool.py --mode source
python scripts/research_exiftool_tags.py --make Nikon --counters-only
```

This prints every candidate tag with its table, tag id, exact line number, data
format, any model condition, and the source's own notes. Read the notes
carefully - they are where a source tells you a field is only valid for some
models, or means something other than what its name suggests.

## Writing the entry

Registry files live in `src/camera_count/registry/camera_database/<make>.yaml`.

```yaml
models:
  - model: "NIKON Z 6_2"          # exactly as the camera reports it
    aliases: ["Nikon Z6 II"]      # other names, for lookup only
    exact_count_available: true
    methods:
      - type: makernote_field     # or ptp_property / ptp_operation
        identifier: "Nikon:ShutterCount"   # exact Group:Tag, or a hex code
        count_type: total_releases         # what the manufacturer says it counts
        verification_status: documented
        firmware_range: ">=1.30"           # optional
        invalid_values: [4294965247]       # optional documented "n/a" values
        citation:
          kind: source_ref
          reference: exiftool/lib/Image/ExifTool/Nikon.pm:2975
          note: >-
            What the source actually says. Quote it rather than summarising it.
    limitations:
      - Anything the source warns about, in the buyer's words.
```

### Choosing `count_type`

Use what the source says the counter counts, not what you would like it to be.
If the note says "includes electronic + mechanical shutter", that is
`total_releases`, not `mechanical`. If the source does not say, that is a reason
to ask before registering it.

### The wildcard model

`model: "*"` means the method is documented in a manufacturer's **main**
MakerNotes table rather than per model. It is used only when no exact model
entry matches, and it still reports unavailable when the field is absent from
the file. Use it only when the source really is manufacturer-wide.

### `ptp_operation` methods

An operation also needs a `value` block saying where the integer sits in the
answer, and that shape must come from the same documentation as the citation:

```yaml
        value:
          source: response_parameter   # or data_uint32
          index: 1                     # or offset: 4
```

## Adding a fixture

Put an ExifTool JSON output or a recorded, redacted transaction under
`tests/fixtures/`. Do not attach an original image unless you own it and are
happy for it to be redistributed under this repository's licence.

```powershell
exiftool -j -n -G1 -a -u YOURFILE.NEF > tests/fixtures/<make>-<model>.json
```

Redact the serial number before committing.

## Checking your work

```powershell
uv run pytest
uv run python scripts/generate_support_docs.py
uv run camera-count supported --make <Make>
```

The loader is strict on purpose: `exact_count_available` must follow the
evidence, a `ptp_operation` without a value location is rejected, and duplicate
models or source ids are errors.

## Hardware verification

A model becomes `hardware_verified` only through a pull request containing a row
in [hardware-test-matrix.md](hardware-test-matrix.md). The procedure is
performed by a human, on the camera:

1. Read the count.
2. Press the shutter **N** times yourself. The software never triggers it.
3. Read again, and confirm the difference is exactly N.
4. Compare with a manufacturer service reading where you can.

## What gets a PR rejected

- No citation, or a citation that does not say what the entry claims
- `hardware_verified` without a matrix row
- A `count_type` the source does not support
- A field whose source warns it is only valid for some models or some copies,
  registered as though it were reliable
- Anything that makes the tool produce a number it cannot justify
