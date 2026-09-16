# Camera Count Tool

**Camera Count Tool reports a shutter count only when it can obtain that count from an authoritative source. When an exact count cannot be obtained, the software reports it as unavailable rather than estimating it.**

Buying a used camera means trusting a number. This tool refuses to invent one.
It reads the exact shutter/actuation count directly from a connected camera, or
from an original camera file, and shows nothing at all when it cannot.

**Windows 10 and 11 (x64).**

- **Offline.** No network access anywhere in the program. No accounts, no telemetry, no uploads.
- **Read-only.** It never changes a setting, releases the shutter, writes to the card, touches firmware, or resets a counter. Every protocol operation is checked against a read-only allow-list before it is sent.
- **No driver changes.** It talks to the camera through Windows Portable Devices, the path Windows already uses. It never installs, replaces, or removes a driver.
- **Cited.** Every number traces to a specific documented source - a device property, a vendor operation, or a manufacturer MakerNotes field - recorded in the camera registry with a citation.
- **Binary output.** `VERIFIED EXACT COUNT` with an integer, or `EXACT COUNT UNAVAILABLE` with a reason. The second one is a correct, successful result.

## What it will never do

No estimation, extrapolation, interpolation, statistics, or machine learning.
No confidence scores or hedging words. No deriving a count from image numbers,
file names, timestamps, or the number of photos on a card. No adding a
mechanical and an electronic counter together unless the manufacturer documents
that the sum means something.

If a non-authoritative counter is present in the data, it is shown under a
notice that says exactly what it is - never in a shutter-count slot.

## Install

### Option 1 - download a release (no Python needed)

From the [Releases page](https://github.com/Osama01Anwar/camera-count-tool/releases):

| File | What it is |
|---|---|
| `CameraCountTool-<version>-windows-x64-setup.exe` | Installer. Adds the desktop app and the `camera-count` command. |
| `CameraCountTool-<version>-windows-x64-portable.zip` | Unzip and run. Nothing is written outside the folder except your local results database. |

Every release ships `SHA256SUMS.txt`. Check it before you run anything.

Releases are not code-signed, so Windows SmartScreen will warn on first run.
Choose **More info → Run anyway**, or verify the SHA-256 first.

### Option 2 - install from this repository with Python 3.12+

```powershell
uv tool install git+https://github.com/Osama01Anwar/camera-count-tool
# or
pipx install git+https://github.com/Osama01Anwar/camera-count-tool
```

This gives you the `camera-count` command and the `camera-count-gui` desktop
app. Installing this way expects [ExifTool](https://exiftool.org) on your
`PATH` for image mode; the packaged releases bundle it.

## Use it

```powershell
camera-count detect                 # what is connected, and how
camera-count inspect                # identify the camera (model, serial, firmware)
camera-count count                  # the counters, each one exact or NOT AVAILABLE
camera-count exif PHOTO.NEF         # exact historical count from an original file
camera-count report --format pdf --out report.pdf
camera-count supported --make Nikon # which models have a documented method
camera-count diagnostics --export log.json
```

Exit codes: `0` an exact count was found, `2` no exact count is available (not an
error), `1` something failed.

Add `--json` to any command for machine-readable output.

## Connecting the camera

Set the camera's USB mode to **PTP / PC Remote / MTP**. Mass-storage mode gives
no protocol access, and the tool will say so.

If File Explorer or another program is holding the camera, close it and run
`camera-count detect` again - this tool will tell you what has the device
rather than forcing it free. See [docs/usb-debugging.md](docs/usb-debugging.md).

Cameras that only work through a vendor-installed WinUSB driver are supported
through an optional libusb backend: `uv pip install "camera-count-tool[winusb]"`.
This program will never install that driver for you.

## Supported cameras

[docs/manufacturer-support.md](docs/manufacturer-support.md) is generated from
the camera registry and lists, per model, whether a documented exact-count
method exists and which source documents it. Models marked
`hardware_verified` have been confirmed against a physical body with a recorded
before/after test in [docs/hardware-test-matrix.md](docs/hardware-test-matrix.md).

A model that is not listed reports `EXACT SHUTTER COUNT NOT AVAILABLE`. That is
the intended behaviour, not a bug - though a citation-backed
[new camera model issue](https://github.com/Osama01Anwar/camera-count-tool/issues/new/choose)
is very welcome.

## Documentation

- [Architecture](docs/architecture.md)
- [Shutter-count methodology](docs/shutter-count-methodology.md)
- [Protocols](docs/protocols.md) | [EXIF and MakerNotes](docs/exif.md)
- [Adding a camera model](docs/adding-camera-model.md) | [Testing](docs/testing.md) | [Building](docs/building.md)
- [Limitations](docs/limitations.md) | [FAQ](docs/faq.md)

## Licence

Apache-2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
