# EXIF and MakerNotes

## How ExifTool is run

```
exiftool -j -n -G1 -a -u -charset filename=utf8 -@ <argument file>
```

| Flag | Why |
|---|---|
| `-j` | JSON output |
| `-n` | Numeric values, so a count is an integer rather than a formatted string |
| `-G1` | Family-1 group names, so a tag is identified as `Nikon:ShutterCount` rather than the ambiguous `ShutterCount` |
| `-a` | Extract duplicate tags |
| `-u` | Extract unknown tags |
| `-charset filename=utf8` with `-@` | Paths with spaces and non-ASCII characters survive on Windows |

It is invoked as a separate process with an explicit argument list - never a
shell - under a timeout, and only ever to read.

### Why group names matter

`ShutterCount` on its own is not an identifier: several manufacturers define a
tag with that name, and they are different tags with different meanings. The
registry names `Group:Tag` exactly, and matching is exact. A similar name in a
different group is a different field, and the program does not go looking for
near misses.

### Duplicates

With `-a`, a file can contain more than one tag with the same name. ExifTool
suppresses duplicates in JSON output itself (`exiftool:2688-2689`), so each
`Group:Tag` key appears once, resolved by ExifTool's own priority rules. The
lookup is therefore unambiguous.

## The originality checks

They run before any field is read, and a file that fails yields no count.

| Check | What it looks at | Why |
|---|---|---|
| Camera identification | EXIF `Make` and `Model` | Without a model, no model-specific field can be trusted |
| MakerNotes | Presence of a manufacturer group | MakerNotes are stripped when a file is exported or re-saved |
| Editing software | `Software`, `ProcessingSoftware`, `CreatorTool` | A camera writes its firmware version there; an editor writes its own name |
| File type | `FileType` | A camera writes JPEG, HEIC, TIFF and raw formats; it does not write PNG or WebP |
| Dimensions | `ImageWidth`/`Height` against `ExifImageWidth`/`Height` | A resized file has been through software. JPEG and HEIC only - in a raw file the EXIF size may describe an embedded preview |
| Metadata integrity | ExifTool warnings | Truncated or corrupt metadata is not evidence. `[minor]` warnings are tolerated |

Each check reports what it saw, so a rejection can be understood and argued
with rather than just accepted.

## Reading the counter

For the identified `Make` and `Model`, the registry is consulted for methods of
type `makernote_field`. Each names a `Group:Tag`. The value must be a plain
non-negative integer; a string, a float, a list, or anything with punctuation in
it is refused rather than coerced.

Some documented counters have a documented "not available" value - Nikon's
`ShutterCount` maps 4294965247 to `n/a`, for instance. Those values are listed
in the registry as `invalid_values` and reported as unavailable, not as a count.

Some values are stored encrypted: Pentax's counter is a big-endian integer
obfuscated with the capture date and time. ExifTool decrypts it, and because
`-n` disables only the print conversion, the decrypted integer is what arrives.

## Counters that are not shutter counts

`FileIndex`, `FileNumber`, `ImageNumber`, `FrameNumber`, `SequenceNumber`,
`ImageCount`, `DirectoryIndex` and similar fields are collected separately and
shown under:

> Image counter detected - not an authoritative shutter-count source.

They count saved images or file positions. Deleting, formatting, shooting
raw+JPEG, bracketing and in-camera processing all break any relationship with
actuations. They can never fill a counter slot.

## ExifTool as a source

The ExifTool tag tables are the most carefully maintained public record of which
MakerNotes field means what, for which model. Registry entries cite them by file
and line, for example:

```
exiftool/lib/Image/ExifTool/Nikon.pm:2975
```

`scripts/research_exiftool_tags.py` reports every candidate tag with its table,
id and line so that a human can judge it. It does not write registry entries:
"ExifTool has a tag called ShutterCount" is evidence, not a licence to report a
number for every camera on earth.
