# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First working version. Windows 10/11 x64.

### Reading an exact count

- **Image mode.** ExifTool reads an original camera file, originality checks run
  first, and only the exact `Group:Tag` field the registry names for that model
  is read.
- **Camera mode.** Windows Portable Devices reads device identity and
  vendor-extended device properties, and sends documented vendor read
  operations through the MTP passthrough.
- **Registry** of documented methods, each with a file-and-line citation:
  Nikon (`ShutterCount`, `MechanicalShutterCount`), Pentax/Ricoh
  (`ShutterCount`, decrypted), and Canon EOS R5, R6, R6 Mark II, R8 and R50.
- Manufacturers with no documented counter - Fujifilm, Olympus/OM System,
  Panasonic, Leica, Sigma, Hasselblad, Phase One - record that as a researched
  conclusion rather than an omission. Sony's fields are model-conditional and
  are deliberately not registered yet.

### Refusing to guess

- A `ShutterReading` can only be built through a factory that resolves a source
  id to a documented or hardware-verified registry entry.
- The counter type comes from the registry, never from the caller.
- Counters are reported separately and never combined.
- Documented "not available" sentinel values are reported as unavailable.
- Image counters such as `FileNumber` are shown under a notice and can never
  fill a counter slot.
- The build fails if estimation vocabulary appears in shipped code.

### Read-only by construction

- The transport interface has no outbound data parameter.
- Every operation is checked against an allow-list before it is sent, and
  refusals are logged.
- The device is opened with `WPD_CLIENT_DESIRED_ACCESS = GENERIC_READ`.
- The write-side MTP command keys are not defined anywhere in the package.

### Offline and bounded

- No network access anywhere in shipped code, enforced by an AST-walking test.
- Every parser checks its bounds before slicing and is fuzzed with Hypothesis.
- ExifTool runs as a separate process with an argument list and a timeout.

### Interfaces

- `camera-count` with `detect`, `inspect`, `count`, `exif`, `report`,
  `supported`, `diagnostics`; exit codes 0 found / 2 unavailable / 1 error, and
  `--json` everywhere.
- A desktop app with light and dark themes, hot-plug detection and keyboard
  shortcuts.
- Used Camera Inspection Report in HTML, PDF and JSON, sharing one content
  SHA-256.
- Local SQLite storage whose constraints refuse an unsourced count.

### Packaging

- One-folder Windows distribution with both executables, a portable zip, an
  Inno Setup installer, and SHA256SUMS.
- `packaging/verify_release.py` refuses a build that contains mock code, ships
  test packages, lacks the registry or ExifTool, or cannot run with Python
  removed from PATH.

[Unreleased]: https://github.com/Osama01Anwar/camera-count-tool/commits/main
