# Security policy

## Reporting a vulnerability

Please report privately through GitHub's
[security advisory form](https://github.com/Osama01Anwar/camera-count-tool/security/advisories/new).
Do not open a public issue.

Include: what you did, what happened, the affected version and OS, and a
proof-of-concept if you have one. Expect an acknowledgement within a few days.

## Threat model

This program treats **all camera data and all file data as untrusted input**. A
camera on a USB port is an unauthenticated peripheral that can return arbitrary
bytes; an image file can be crafted by anyone.

Defences in place:

- Bounded reads: a maximum container size, maximum array lengths, and an explicit
  length check before every slice. Violations raise `ParseError`.
- Property-based fuzz tests (Hypothesis) over every parser.
- No `shell=True`, no `os.system`, no `eval`/`exec`. ExifTool is invoked as an
  argument list with a timeout.
- Path validation with traversal rejection; files are opened read-only; file
  size and memory use are capped.
- Timeouts on every USB transfer and every subprocess call.
- No network access at all - enforced by a test that walks the AST of shipped code.

## What the software will not do

It never writes to the camera: no setting changes, no shutter release, no file
deletion or modification, no formatting, no firmware access, no counter reset,
no service data writes. Protocol operations are checked against a per-adapter
read-only allow-list before transmission.

## Privacy

Everything stays on the machine. The local SQLite database holds inspection
results and whatever notes you type into a report. Diagnostics exports redact
serial numbers unless you explicitly opt in.

## Supported versions

The latest released version receives fixes. Pre-1.0, there are no backports.
