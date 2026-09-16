# Architecture

The program exists to answer one question - *what is this camera's exact
shutter count?* - and to refuse to answer it badly. Almost every structural
decision below follows from that.

## The shape of it

```
                    camera on USB              original camera file
                          |                             |
                    usb/ (enumerate)              metadata/ (ExifTool)
                          |                             |
             wpd/ session  |  ptp/ session        originality checks
                          |                             |
                    adapters/ (per manufacturer)        |
                          \                            /
                           \       registry/          /
                            \   (what is documented) /
                             \         |            /
                              core/ ShutterReading factory
                                       |
                        reading with a citation, or Unavailable with a reason
                                       |
                     cli/      gui/      report/      db/
```

## Packages

| Package | Responsibility |
|---|---|
| `core` | Result types, the construction guard, fixed messages, errors. Depends on nothing else. |
| `registry` | The camera database: what is documented, for which model, and where that is written down. |
| `usb` | Enumerating devices and explaining why one is unreachable. |
| `wpd` | Windows Portable Devices: cited constants and a read-only session. |
| `ptp` | A minimal read-only PTP implementation for the optional WinUSB path. |
| `adapters` | One module per manufacturer; the mechanism lives in `adapters/base.py`. |
| `metadata` | Running ExifTool, deciding whether a file is original, reading registry-named fields. |
| `link` | The three read-only capabilities an adapter needs, so it does not care which transport it has. |
| `inspection` | One end-to-end inspection: detect, identify, look up, read. |
| `report` | The Used Camera Inspection Report in HTML, PDF and JSON. |
| `db` | Local SQLite storage. |
| `diagnostics` | The protocol transaction log and its redacted export. |
| `cli`, `gui` | Two front ends over the same results. |

Dependencies point one way: `core` knows about nothing, and the front ends know
about everything.

## The guard

A `ShutterReading` cannot be constructed directly. The only way to make one is:

```python
ShutterReading.from_source(value=..., source_id=..., transaction_ref=...)
```

which resolves the source id through the registry and raises unless the entry's
`verification_status` is `documented` or `hardware_verified`. Direct
construction raises `ForbiddenConstructionError`.

The counter kind is taken *from the registry entry*, not from the caller, so no
code path can decide that a number it just read is "the mechanical count".

The same rule is enforced again in SQL: `shutter_readings` has a `CHECK`
constraint that refuses a row with a value but no cited, trusted source.

## The read-only guarantee

Three layers, none of which relies on remembering to be careful:

1. **The transport interface has no data-out parameter.** There is no argument
   through which caller bytes could reach the camera.
2. **Every operation passes an allow-list** before it is sent, and a refusal is
   recorded in the transaction log. Adapters start with an empty vendor
   allow-list.
3. **Windows is told.** The WPD session opens the device with
   `WPD_CLIENT_DESIRED_ACCESS = GENERIC_READ`, so the operating system knows
   this program asked for read access only. The write-side MTP command keys are
   not defined anywhere in the package.

## Untrusted input

A camera on a USB port is an unauthenticated peripheral, and an image file can
be crafted by anyone. Parsers therefore check every bound before slicing, cap
every length they read off the wire, and raise `ParseError` rather than
allocating whatever a device asked for. Hypothesis fuzz tests assert that the
parsers raise `ParseError` and nothing else, for any input at all.

## Two paths to a count

**From the camera.** Windows exposes a vendor-extended MTP device property as a
WPD property whose key is the vendor GUID plus the MTP property code, so a
documented `ptp_property` method is a direct property read. Documented
`ptp_operation` methods go through the read-side MTP passthrough commands.

**From a file.** ExifTool reads the metadata; the originality checks run first;
then only the exact `Group:Tag` field the registry names for that model is read.
A file that fails the originality checks yields no count at all.

## Why the registry is data

Knowledge about cameras changes far more often than the code that reads them,
and it needs reviewing by people who know cameras rather than Python. So the
per-manufacturer adapter modules are nearly empty, and everything specific
lives in `registry/camera_database/*.yaml` next to the citation it came from.
Adding a camera is a data change with a citation, not a code change.

## Further reading

- [Shutter-count methodology](shutter-count-methodology.md)
- [Protocols](protocols.md)
- [EXIF and MakerNotes](exif.md)
- [Limitations](limitations.md)
